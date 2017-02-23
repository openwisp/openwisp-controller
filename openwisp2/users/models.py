import uuid

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group as BaseGroup
from django.contrib.auth.models import UserManager as BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from organizations.abstract import (AbstractOrganization,
                                    AbstractOrganizationOwner,
                                    AbstractOrganizationUser)


class UserManager(BaseUserManager):
    def _create_user(self, *args, **kwargs):
        """
        adds automatic email address object creation to django
        management commands "create_user" and "create_superuser"
        """
        user = super(UserManager, self)._create_user(*args, **kwargs)
        self._create_email(user)
        return user

    def _create_email(self, user):
        """
        creates verified and primary email address objects
        """
        if user.email:
            set_primary = EmailAddress.objects.filter(user=user, primary=True).count() == 0
            email = EmailAddress.objects.create(user=user, email=user.email, verified=True)
            if set_primary:
                email.set_as_primary()


class User(AbstractUser):
    """
    OpenWISP2 User model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bio = models.TextField(_('bio'), blank=True)
    url = models.URLField(_('URL'), blank=True)
    company = models.CharField(_('company'), max_length=30, blank=True)
    location = models.CharField(_('location'), max_length=128, blank=True)

    objects = UserManager()

    @cached_property
    def organizations_pk(self):
        """
        returns primary keys of organizations the user is associated to
        """
        manager = OrganizationUser.objects
        qs = manager.filter(user=self, organization__is_active=True) \
                    .select_related() \
                    .only('organization_id') \
                    .values_list('organization_id')
        return qs


class Group(BaseGroup):
    """
    Proxy model used to move ``GroupAdmin``
    under the same app label as the other models
    """
    class Meta:
        proxy = True
        verbose_name = _('group')
        verbose_name_plural = _('groups')


class Organization(AbstractOrganization):
    """
    OpenWISP2 Organization model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField(_('description'), blank=True)
    email = models.EmailField(_('email'), blank=True)
    url = models.URLField(_('URL'), blank=True)


class OrganizationUser(AbstractOrganizationUser):
    """
    OpenWISP2 OrganizationUser model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class OrganizationOwner(AbstractOrganizationOwner):
    """
    OpenWISP2 OrganizationOwner model
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
