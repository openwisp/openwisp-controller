from django.db import models
from django.utils.translation import gettext_lazy as _
from django_x509.base.models import AbstractCa as BaseCa
from django_x509.base.models import AbstractCert as BaseCert
from swapper import get_model_name

from openwisp_users.mixins import ShareableOrgMixin

from ..utils import UnqiueCommonNameMixin


# Avoids "DateTimeField received a naive datetime while time zone support is active"
# warning by returning an aware datetime when USE_TZ is True.
def default_validity_start():
    from datetime import datetime, timedelta
    from django.conf import settings
    from django.utils import timezone
    start = datetime.now() - timedelta(days=1)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if settings.USE_TZ:
        return timezone.make_aware(start)
    return start


class AbstractCa(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCa):
    validity_start = models.DateTimeField(
        blank=True, null=True, default=default_validity_start
    )

    class Meta(BaseCa.Meta):
        abstract = True
        constraints = [
            models.UniqueConstraint(
                fields=["common_name", "organization"],
                name="%(app_label)s_%(class)s_comman_name_and_organization_is_unique",
            ),
        ]


class AbstractCert(ShareableOrgMixin, UnqiueCommonNameMixin, BaseCert):
    validity_start = models.DateTimeField(
        blank=True, null=True, default=default_validity_start
    )
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

    def clean(self):
        self._validate_org_relation("ca")
