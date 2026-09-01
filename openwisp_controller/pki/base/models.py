from contextlib import nullcontext

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from django_x509.base.models import AbstractCa as BaseCa
from django_x509.base.models import AbstractCert as BaseCert
from swapper import get_model_name, load_model

from openwisp_users.mixins import ShareableOrgMixin

from ..utils import UnqiueCommonNameMixin


def _atomic_if_needed():
    if transaction.get_connection().in_atomic_block:
        return nullcontext()
    return transaction.atomic()


class AbstractCa(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCa):
    class Meta(BaseCa.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["common_name", "organization"],
                name="%(app_label)s_%(class)s_comman_name_and_organization_is_unique",
            ),
        ]

    def renew(self):
        if self._state.adding or not self.pk:
            return super().renew()
        with _atomic_if_needed():
            locked = self.__class__.objects.select_for_update().get(pk=self.pk)
            BaseCa.renew(locked)
            self._sync_generated_fields(locked)

    def _sync_generated_fields(self, ca):
        for field in self._meta.concrete_fields:
            setattr(self, field.attname, getattr(ca, field.attname))
        for attr in ("x509", "pkey", "x509_text"):
            self.__dict__.pop(attr, None)


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
        if self._state.adding and self.ca_id:
            with _atomic_if_needed():
                self._lock_current_ca()
                self._regenerate_if_signed_by_stale_ca()
                super().save(*args, **kwargs)
        else:
            super().save(*args, **kwargs)
        if update_fields is None or {"organization", "organization_id"}.intersection(
            update_fields
        ):
            self._initial_organization_id = self.organization_id

    def full_clean(self, *args, **kwargs):
        if (
            self._state.adding
            and self.ca_id
            and self.certificate
            and getattr(self, "_generated_by_model", False)
        ):
            with _atomic_if_needed():
                self._lock_current_ca()
                self._regenerate_if_signed_by_stale_ca()
                super().full_clean(*args, **kwargs)
        else:
            super().full_clean(*args, **kwargs)

    def _generate(self):
        super()._generate()
        self._generated_by_model = True

    def _lock_current_ca(self):
        ca_model = self._meta.get_field("ca").remote_field.model
        self.ca = ca_model.objects.select_for_update().get(pk=self.ca_id)

    def _regenerate_if_signed_by_stale_ca(self):
        if not self.certificate:
            return
        try:
            self._verify_ca()
        except ValidationError:
            if not getattr(self, "_generated_by_model", False):
                raise
            self._clear_generated_material()

    def _clear_generated_material(self):
        self.certificate = ""
        self.private_key = ""
        for attr in ("x509", "pkey", "x509_text"):
            self.__dict__.pop(attr, None)

    def clean(self):
        self._validate_org_relation("ca")
        self._validate_bound_cert_organization()

    def _validate_bound_cert_organization(self):
        """
        Defers to ``config.DeviceCertificate`` to prevent moving a
        certificate to another organization while it is assigned to a device.
        """
        DeviceCertificate = load_model("config", "DeviceCertificate", required=False)
        if DeviceCertificate is None:
            return
        DeviceCertificate.validate_cert_bound_organization(self)
