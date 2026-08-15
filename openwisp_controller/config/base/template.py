import json
import logging
from collections import OrderedDict
from copy import copy

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models, transaction
from django.db.models import JSONField, Prefetch
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

_ORGANIZATION_UNSET = object()

TYPE_CHOICES = (
    ("generic", _("Generic")),
    ("vpn", _("VPN-client")),
    ("cert", _("Certificate generator")),
)


def default_auto_cert():
    """
    returns the default value for auto_cert field
    (this avoids to set the exact default value in the database migration)
    """
    return DEFAULT_AUTO_CERT


def get_unassigned_certs():
    Cert = load_model("django_x509", "Cert")
    DeviceCertificate = load_model("config", "DeviceCertificate")
    assigned_cert_ids = DeviceCertificate.objects.filter(
        cert_id__isnull=False
    ).values_list("cert_id", flat=True)
    return {
        "pk__in": Cert.objects.exclude(id__in=assigned_cert_ids),
        "revoked": False,
    }


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
    ca = models.ForeignKey(
        get_model_name("django_x509", "Ca"),
        on_delete=models.CASCADE,
        verbose_name=_("Certificate Authority"),
        blank=True,
        null=True,
        help_text=_(
            "The Certificate Authority that will sign certificates generated "
            "by this template."
        ),
    )
    blueprint_cert = models.ForeignKey(
        get_model_name("django_x509", "Cert"),
        on_delete=models.RESTRICT,
        verbose_name=_("Blueprint Certificate"),
        blank=True,
        null=True,
        limit_choices_to=get_unassigned_certs,
        help_text=_(
            "Optional: Select an unassigned certificate to copy extensions and "
            "properties from."
        ),
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
    notes = models.TextField(blank=True, help_text=_("internal notes"))
    # auto_cert naming kept for backward compatibility
    auto_cert = models.BooleanField(
        _("automatic tunnel provisioning"),
        default=default_auto_cert,
        db_index=True,
        help_text=_(
            "whether tunnel specific configuration (cryptographic keys, ip addresses, "
            "etc) should be automatically generated and managed behind the scenes "
            "for each configuration using this template, valid only for the VPN and "
            "certificate template types"
        ),
    )
    default_values = JSONField(
        _("Default Values"),
        default=dict,
        blank=True,
        help_text=_(
            "Define default values for the variables used in this template. "
            "These values are used during validation and when a variable is "
            "not provided by the device, group, or organization."
        ),
        encoder=DjangoJSONEncoder,
    )
    _changed_checked_fields = [
        "ca_id",
        "blueprint_cert_id",
        "type",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields()

    def _is_deferred(self, field):
        return field in self.get_deferred_fields()

    def _expand_update_field_attnames(self, update_fields):
        """
        Expands ``update_fields`` so both the relation name (e.g. ``ca``) and
        the column attname (e.g. ``ca_id``) are recognized.
        """
        from django.core.exceptions import FieldDoesNotExist

        expanded = set(update_fields)
        for name in update_fields:
            try:
                model_field = self._meta.get_field(name)
            except FieldDoesNotExist:
                continue
            expanded.add(model_field.name)
            expanded.add(model_field.attname)
        return expanded

    def _set_initial_values_for_changed_checked_fields(self, update_fields=None):
        if update_fields is not None:
            update_fields = self._expand_update_field_attnames(update_fields)
        for field in self._changed_checked_fields:
            if update_fields is not None and field not in update_fields:
                continue
            if self._is_deferred(field):
                setattr(self, f"_initial_{field}", models.DEFERRED)
            else:
                setattr(self, f"_initial_{field}", getattr(self, field))

    def save(self, *args, **kwargs):
        # update_fields can be passed by name or as the 4th save() argument.
        # Keep the same style when adding auto_cert below.
        update_fields = kwargs.get("update_fields")
        is_positional = False
        if update_fields is None and len(args) > 3:
            update_fields = args[3]
            is_positional = True
        if self.type == "cert":
            self.auto_cert = True
            if update_fields is not None and "auto_cert" not in update_fields:
                update_fields = {*update_fields, "auto_cert"}
                if is_positional:
                    args = list(args)
                    args[3] = update_fields
                    args = tuple(args)
                else:
                    kwargs["update_fields"] = update_fields
        super().save(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields(update_fields=update_fields)

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._set_initial_values_for_changed_checked_fields()

    def _get_initial_value_or_fallback(self, field):
        initial = getattr(self, f"_initial_{field}", None)
        if initial == models.DEFERRED:
            if not self.pk:
                return None
            query_field = field[:-3] if field.endswith("_id") else field
            try:
                obj = self.__class__.objects.only(query_field).get(pk=self.pk)
                val = getattr(obj, field)
                setattr(self, f"_initial_{field}", val)
                return val
            except self.__class__.DoesNotExist:
                return None
        return initial

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
        DeviceCertificate = load_model("config", "DeviceCertificate")
        with transaction.atomic():
            for config in (
                self.config_relations.prefetch_related(
                    Prefetch(
                        "device_certificate_relations",
                        queryset=DeviceCertificate.objects.select_related(
                            "template", "cert"
                        ).order_by("created"),
                    ),
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
                    with transaction.atomic():
                        config.templates.add(self)
                except Exception as e:
                    # Log error but continue with other configs
                    logger.exception(
                        f"Failed to add template {self.pk} to "
                        f"config {config.pk}: {e}"
                    )

    def _validate_cert_template_changes(self):
        """
        Prevents changing cert-specific settings of a certificate template
        if it is already assigned to active devices.
        """
        if self._state.adding:
            return
        initial_ca_id = self._get_initial_value_or_fallback("ca_id")
        initial_blueprint_cert_id = self._get_initial_value_or_fallback(
            "blueprint_cert_id"
        )
        initial_type = self._get_initial_value_or_fallback("type")
        changing_protected_fields = (
            initial_ca_id != self.ca_id
            or initial_blueprint_cert_id != self.blueprint_cert_id
            or (initial_type == "cert" and self.type != "cert")
        )
        if not changing_protected_fields:
            return

        Config = load_model("config", "Config")
        if not (
            Config.objects.filter(templates=self)
            .exclude(status__in=["deactivating", "deactivated"])
            .exists()
        ):
            return

        errors = {}
        if initial_ca_id != self.ca_id:
            errors["ca"] = _(
                "This template is already assigned to active devices. "
                "You cannot change the CA on an active template."
            )
        if initial_blueprint_cert_id != self.blueprint_cert_id:
            errors["blueprint_cert"] = _(
                "This template is already assigned to active devices. "
                "You cannot change the Blueprint Certificate "
                "on an active template."
            )
        if initial_type == "cert" and self.type != "cert":
            errors["type"] = _(
                "This template is already assigned to active devices. "
                "You cannot change the template type from certificate "
                "on an active template."
            )
        if errors:
            raise ValidationError(errors)

    def _clean_cert_template(self):
        """
        Validates requirements specific to templates of type 'cert'.
        Clears cert-related fields if the type is not 'cert'.
        """
        if self.type == "cert":
            self._validate_org_relation("ca")
            self._validate_org_relation("blueprint_cert")
            if not self.ca:
                raise ValidationError(
                    {
                        "ca": _(
                            "A Certificate Authority is required when the template "
                            "type is certificate."
                        )
                    }
                )
            if self.blueprint_cert and self.blueprint_cert.ca_id != self.ca_id:
                raise ValidationError(
                    {
                        "blueprint_cert": _(
                            "The selected certificate must match the selected "
                            "Certificate Authority."
                        )
                    }
                )
            if self.blueprint_cert and self.blueprint_cert.revoked:
                raise ValidationError(
                    {
                        "blueprint_cert": _(
                            "Please select a non-revoked certificate to use as "
                            "a blueprint."
                        )
                    }
                )
            if self.blueprint_cert_id:
                DeviceCertificate = load_model("config", "DeviceCertificate")
                if DeviceCertificate.objects.filter(
                    cert_id=self.blueprint_cert_id
                ).exists():
                    raise ValidationError(
                        {
                            "blueprint_cert": _(
                                "This certificate is already assigned to a device. "
                                "Please select an unassigned certificate to "
                                "use as a blueprint."
                            )
                        }
                    )
            if self.config is None:
                self.config = {}
        else:
            self.ca = None
            self.blueprint_cert = None

    def clean(self, *args, **kwargs):
        """
        * validates org relationship of VPN if present
        * validates default_values field
        * ensures VPN is selected if type is VPN
        * clears VPN specific fields if type is not VPN
        * automatically determines configuration if necessary
        * if flagged as required forces it also to be default
        * prevents mutating cert-specific fields on active cert templates
        * enforces CA and Blueprint requirements for cert templates
        """
        self._validate_cert_template_changes()
        self._clean_cert_template()
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
            if self.type != "cert":
                self.auto_cert = False
        if self.type == "cert":
            self.auto_cert = True
        if self.type == "vpn" and not self.config:
            self.config = self.vpn.auto_client(
                auto_cert=self.auto_cert, template_backend_class=self.backend_class
            )
        if self.required and not self.default:
            self.default = True
        super().clean(*args, **kwargs)
        if not self.config and self.type != "cert":
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

    def clone(self, user, organization=_ORGANIZATION_UNSET):
        clone = copy(self)
        if organization is not _ORGANIZATION_UNSET:
            clone.organization = organization
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
