import json
import logging
from collections import OrderedDict
from copy import copy

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _
from netjsonconfig.exceptions import ValidationError as NetjsonconfigValidationError
from swapper import get_model_name, load_model
from taggit.managers import TaggableManager

from ...base import ShareableOrgMixinUniqueName
from ..settings import DEFAULT_AUTO_CERT
from ..tasks import (
    auto_add_template_to_existing_configs,
    update_template_related_config_status,
)
from .base import BaseConfig

logger = logging.getLogger(__name__)

TYPE_CHOICES = (("generic", _("Generic")), ("vpn", _("VPN-client")))


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
        through=get_model_name("config", "TaggedTemplate"),
        blank=True,
        help_text=_(
            "A comma-separated list of template tags, may be used "
            "to ease auto configuration with specific settings (eg: "
            "4G, mesh, WDS, VPN, ecc.)"
        ),
    )
    vpn = models.ForeignKey(
        get_model_name("config", "Vpn"),
        verbose_name=_("VPN"),
        blank=True,
        null=True,
        on_delete=models.CASCADE,
    )
    type = models.CharField(
        _("type"),
        max_length=16,
        choices=TYPE_CHOICES,
        default="generic",
        db_index=True,
        help_text=_("template type, determines which features are available"),
    )
    default = models.BooleanField(
        _("enabled by default"),
        default=False,
        db_index=True,
        help_text=_(
            "whether this template is applied to all current and future devices"
            " by default (can be unassigned manually)"
        ),
    )
    required = models.BooleanField(
        _("required"),
        default=False,
        db_index=True,
        help_text=_(
            "if checked, will force the assignment of this template to all the "
            "devices of the organization (if no organization is selected, it will "
            "be required for every device in the system)"
        ),
    )
    # auto_cert naming kept for backward compatibility
    auto_cert = models.BooleanField(
        _("automatic tunnel provisioning"),
        default=default_auto_cert,
        db_index=True,
        help_text=_(
            "whether tunnel specific configuration (cryptographic keys, ip addresses, "
            "etc) should be automatically generated and managed behind the scenes "
            "for each configuration using this template, valid only for the VPN type"
        ),
    )
    default_values = JSONField(
        _("Default Values"),
        default=dict,
        blank=True,
        help_text=_(
            "A dictionary containing the default "
            "values for the variables used by this "
            "template; these default variables will "
            "be used during schema validation."
        ),
        encoder=DjangoJSONEncoder,
    )
    __template__ = True

    class Meta:
        abstract = True
        verbose_name = _("template")
        verbose_name_plural = _("templates")
        unique_together = (("organization", "name"),)

    @classmethod
    def pre_save_handler(cls, instance, *args, **kwargs):
        """
        Modifies status of related configs
        """
        try:
            current = cls.objects.get(id=instance.id)
        except cls.DoesNotExist:
            return
        if hasattr(instance, "backend_instance"):
            del instance.backend_instance
        try:
            current_checksum = current.checksum
        except NetjsonconfigValidationError:
            # If the Netjsonconfig library upgrade changes the schema,
            # the old configuration may become invalid, raising an exception.
            # Setting the checksum to None forces related configurations to update.
            current_checksum = None
        instance._should_update_related_config_status = (
            instance.checksum != current_checksum
        )

        # Check if template is becoming default or required
        if (instance.default and not current.default) or (
            instance.required and not current.required
        ):
            instance._should_add_to_existing_configs = True

    @classmethod
    def post_save_handler(cls, instance, created, *args, **kwargs):
        if not created and getattr(
            instance, "_should_update_related_config_status", False
        ):
            transaction.on_commit(
                lambda: update_template_related_config_status.delay(instance.pk)
            )
        # Auto-add template to existing configs if it's new or became default/required
        if getattr(instance, "_should_add_to_existing_configs", False) or (
            created and (instance.default or instance.required)
        ):
            transaction.on_commit(
                lambda: auto_add_template_to_existing_configs.delay(str(instance.pk))
            )

    def _update_related_config_status(self):
        # use atomic to ensure any code bound to
        # be executed via transaction.on_commit
        # is executed after the whole block
        with transaction.atomic():
            for config in (
                self.config_relations.prefetch_related(
                    "vpnclient_set",
                    "templates",
                )
                .select_related("device", "device__organization__config_settings")
                .iterator(chunk_size=1000)
            ):
                config.update_status_if_checksum_changed(
                    send_config_modified_signal=False
                )
                config._send_config_modified_signal(action="related_template_changed")

    def _auto_add_to_existing_configs(self):
        """
        When a template is ``default`` or ``required``, adds the template
        to each relevant ``Config`` object
        """
        Config = load_model("config", "Config")

        # Only proceed if template is default or required
        if not (self.default or self.required):
            return

        # use atomic to ensure any code bound to
        # be executed via transaction.on_commit
        # is executed after the whole block
        with transaction.atomic():
            # Exclude deactivating or deactivated configs
            configs = (
                Config.objects.select_related("device")
                .filter(
                    backend=self.backend,
                )
                .exclude(
                    models.Q(status__in=["deactivating", "deactivated"])
                    | models.Q(templates__id=self.pk)
                )
            )
            if self.organization_id:
                configs = configs.filter(device__organization_id=self.organization_id)
            for config in configs.iterator():
                try:
                    config.templates.add(self)
                except Exception as e:
                    # Log error but continue with other configs
                    logger.exception(
                        f"Failed to add template {self.pk} to "
                        f"config {config.pk}: {e}"
                    )

    def clean(self, *args, **kwargs):
        """
        * validates org relationship of VPN if present
        * validates default_values field
        * ensures VPN is selected if type is VPN
        * clears VPN specific fields if type is not VPN
        * automatically determines configuration if necessary
        * if flagged as required forces it also to be default
        """
        self._validate_org_relation("vpn")
        if not self.default_values:
            self.default_values = {}
        if not isinstance(self.default_values, dict):
            raise ValidationError(
                {"default_values": _("the supplied value is not a JSON object")}
            )
        if self.type == "vpn" and not self.vpn:
            raise ValidationError(
                {"vpn": _('A VPN must be selected when template type is "VPN"')}
            )
        elif self.type != "vpn":
            self.vpn = None
            self.auto_cert = False
        if self.type == "vpn" and not self.config:
            self.config = self.vpn.auto_client(
                auto_cert=self.auto_cert, template_backend_class=self.backend_class
            )
        if self.required and not self.default:
            self.default = True
        super().clean(*args, **kwargs)
        if not self.config:
            raise ValidationError(_("The configuration field cannot be empty."))

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
        name = "{} (Clone)".format(self.name)
        index = 2
        while self.__class__.objects.filter(name=name).count():
            name = "{} (Clone {})".format(self.name, index)
            index += 1
        return name


# It's allowed to be blank because VPN client templates can be
# automatically generated via the netjsonconfig library if left empty.
AbstractTemplate._meta.get_field("config").blank = True


def _get_value_for_comparison(value):
    """
    if value is a nested OrderedDict, convert it to dict
    so two simple dicts can be compared
    """
    if not isinstance(value, OrderedDict):
        return value
    return json.loads(json.dumps(value))
