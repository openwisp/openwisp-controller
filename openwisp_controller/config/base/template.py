import json
from collections import OrderedDict
from copy import copy

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from swapper import get_model_name
from taggit.managers import TaggableManager

from ...base import ShareableOrgMixinUniqueName
from ..settings import DEFAULT_AUTO_CERT
from ..tasks import update_template_related_config_status
from .base import BaseConfig

TYPE_CHOICES = (('generic', _('Generic')), ('vpn', _('VPN-client')))


def default_auto_cert():
    """
    returns the default value for auto_cert field
    (this avoids to set the exact default value in the database migration)
    """
    return DEFAULT_AUTO_CERT


class AbstractTemplate(ShareableOrgMixinUniqueName, BaseConfig):
    """
    Abstract model implementing a
    netjsonconfig template
    """

    tags = TaggableManager(
        through=get_model_name('config', 'TaggedTemplate'),
        blank=True,
        help_text=_(
            'A comma-separated list of template tags, may be used '
            'to ease auto configuration with specific settings (eg: '
            '4G, mesh, WDS, VPN, ecc.)'
        ),
    )
    vpn = models.ForeignKey(
        get_model_name('config', 'Vpn'),
        verbose_name=_('VPN'),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    type = models.CharField(
        _('type'),
        max_length=16,
        choices=TYPE_CHOICES,
        default='generic',
        db_index=True,
        help_text=_('template type, determines which features are available'),
    )
    default = models.BooleanField(
        _('enabled by default'),
        default=False,
        db_index=True,
        help_text=_(
            'whether new configurations will have this template enabled by default'
        ),
    )
    required = models.BooleanField(
        _('required'),
        default=False,
        db_index=True,
        help_text=_(
            'if checked, will force the assignment of this template to all the '
            'devices of the organization (if no organization is selected, it will '
            'be required for every device in the system)'
        ),
    )
    # auto_cert naming kept for backward compatibility
    auto_cert = models.BooleanField(
        _('automatic tunnel provisioning'),
        default=default_auto_cert,
        db_index=True,
        help_text=_(
            'whether tunnel specific configuration (cryptographic keys, ip addresses, '
            'etc) should be automatically generated and managed behind the scenes '
            'for each configuration using this template, valid only for the VPN type'
        ),
    )
    default_values = JSONField(
        _('Default Values'),
        default=dict,
        blank=True,
        help_text=_(
            'A dictionary containing the default '
            'values for the variables used by this '
            'template; these default variables will '
            'be used during schema validation.'
        ),
        load_kwargs={'object_pairs_hook': OrderedDict},
        dump_kwargs={'indent': 4},
    )
    __template__ = True

    class Meta:
        abstract = True
        verbose_name = _('template')
        verbose_name_plural = _('templates')
        unique_together = (('organization', 'name'),)

    def save(self, *args, **kwargs):
        """
        modifies status of related configs
        if key attributes have changed (queries the database)
        """
        update_related_config_status = False
        if not self._state.adding:
            current = self.__class__.objects.get(pk=self.pk)
            for attr in ['backend', 'config', 'default_values']:
                new_value = _get_value_for_comparison(getattr(self, attr))
                current_value = _get_value_for_comparison(getattr(current, attr))
                if new_value != current_value:
                    update_related_config_status = True
                    break
        # save current changes
        super().save(*args, **kwargs)
        # update relations
        if update_related_config_status:
            transaction.on_commit(
                lambda: update_template_related_config_status.delay(self.pk)
            )

    def _update_related_config_status(self):
        # use atomic to ensure any code bound to
        # be executed via transaction.on_commit
        # is executed after the whole block
        with transaction.atomic():
            changing_status = list(
                self.config_relations.exclude(status='modified').values_list(
                    'pk', flat=True
                )
            )
            for config in self.config_relations.select_related('device').iterator():
                # config modified signal sent regardless
                config._send_config_modified_signal(action='related_template_changed')
                # config status changed signal sent only if status changed
                if config.pk in changing_status:
                    config._send_config_status_changed_signal()
            self.config_relations.exclude(status='modified').update(status='modified')

    def clean(self, *args, **kwargs):
        """
        * validates org relationship of VPN if present
        * validates default_values field
        * ensures VPN is selected if type is VPN
        * clears VPN specific fields if type is not VPN
        * automatically determines configuration if necessary
        * if flagged as required forces it also to be default
        """
        self._validate_org_relation('vpn')
        if not self.default_values:
            self.default_values = {}
        if not isinstance(self.default_values, dict):
            raise ValidationError(
                {'default_values': _('the supplied value is not a JSON object')}
            )
        if self.type == 'vpn' and not self.vpn:
            raise ValidationError(
                {'vpn': _('A VPN must be selected when template type is "VPN"')}
            )
        elif self.type != 'vpn':
            self.vpn = None
            self.auto_cert = False
        if self.type == 'vpn' and not self.config:
            self.config = self.vpn.auto_client(
                auto_cert=self.auto_cert, template_backend_class=self.backend_class
            )
        if self.required and not self.default:
            self.default = True
        super().clean(*args, **kwargs)
        if not self.config:
            raise ValidationError(_('The configuration field cannot be empty.'))

    def get_context(self, system=False):
        context = {}
        if self.default_values and not system:
            context = copy(self.default_values)
        context.update(self.get_vpn_server_context())
        context.update(super().get_context())
        return context

    def get_system_context(self):
        system_context = self.get_context(system=True)
        return OrderedDict(sorted(system_context.items()))

    def get_vpn_server_context(self):
        try:
            return self.vpn.get_vpn_server_context()
        except (ObjectDoesNotExist, AttributeError):
            return {}

    def clone(self, user):
        clone = copy(self)
        clone.name = self.__get_clone_name()
        clone._state.adding = True
        clone.pk = None
        # avoid cloned templates to be flagged as default
        # to avoid potential unwanted duplications in
        # newly registrated devices
        clone.default = False
        clone.full_clean()
        clone.save()
        return clone

    def __get_clone_name(self):
        name = '{} (Clone)'.format(self.name)
        index = 2
        while self.__class__.objects.filter(name=name).count():
            name = '{} (Clone {})'.format(self.name, index)
            index += 1
        return name


# It's allowed to be blank because VPN client templates can be
# automatically generated via the netjsonconfig library if left empty.
AbstractTemplate._meta.get_field('config').blank = True


def _get_value_for_comparison(value):
    """
    if value is a nested OrderedDict, convert it to dict
    so two simple dicts can be compared
    """
    if not isinstance(value, OrderedDict):
        return value
    return json.loads(json.dumps(value))
