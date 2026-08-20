from django.apps import apps
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_x509.base.models import AbstractCa as BaseCa
from django_x509.base.models import AbstractCert as BaseCert
from swapper import get_model_name, load_model

from openwisp_users.mixins import ShareableOrgMixin

from ..utils import UnqiueCommonNameMixin


class AbstractCa(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCa):
    class Meta(BaseCa.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["common_name", "organization"],
                name="%(app_label)s_%(class)s_comman_name_and_organization_is_unique",
            ),
        ]


class AbstractCert(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCert):
    ca = models.ForeignKey(
        get_model_name("django_x509", "Ca"),
        verbose_name=_("CA"),
        on_delete=models.CASCADE,
    )

    class Meta(BaseCert.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["common_name", "organization"],
                name="%(app_label)s_%(class)s_comman_name_and_organization_is_unique",
            ),
        ]

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        if "organization_id" in field_names:
            instance._initial_organization_id = instance.organization_id
        return instance

    def refresh_from_db(self, using=None, fields=None, **kwargs):
        super().refresh_from_db(using=using, fields=fields, **kwargs)
        if fields is None or {"organization", "organization_id"}.intersection(fields):
            self._initial_organization_id = self.organization_id

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is None and len(args) > 3:
            update_fields = args[3]
        super().save(*args, **kwargs)
        if update_fields is None or {"organization", "organization_id"}.intersection(
            update_fields
        ):
            self._initial_organization_id = self.organization_id

    def clean(self):
        self._validate_org_relation("ca")
        self._validate_bound_cert_organization()

    def _validate_bound_cert_organization(self):
        """
        Defers to ``config.DeviceCertificate`` to prevent moving a
        certificate to another organization while it is assigned to a device.
        """
        if not apps.is_installed("openwisp_controller.config"):
            return
        DeviceCertificate = load_model("config", "DeviceCertificate")
        DeviceCertificate.validate_cert_bound_organization(self)
