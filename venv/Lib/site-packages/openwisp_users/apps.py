import logging

from django.apps import AppConfig
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.utils.translation import gettext_lazy as _
from swapper import get_model_name, load_model

from openwisp_utils import settings as utils_settings
from openwisp_utils.admin_theme.menu import register_menu_group

from . import settings as app_settings

logger = logging.getLogger(__name__)


class OpenwispUsersConfig(AppConfig):
    name = "openwisp_users"
    app_label = "openwisp_users"
    verbose_name = _("Users and Organizations")
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        self.register_menu_group()
        self.set_default_settings()
        self.connect_receivers()

    def register_menu_group(self):
        items = {
            1: {
                "label": _("Users"),
                "model": settings.AUTH_USER_MODEL,
                "name": "changelist",
                "icon": "user",
            },
            2: {
                "label": _("Organizations"),
                "model": get_model_name(self.app_label, "Organization"),
                "name": "changelist",
                "icon": "ow-org",
            },
            3: {
                "label": _("Groups & Permissions"),
                "model": get_model_name(self.app_label, "Group"),
                "name": "changelist",
                "icon": "ow-permission",
            },
        }
        if app_settings.ORGANIZATION_OWNER_ADMIN:
            items[4] = {
                "label": _("Organization Owners"),
                "model": get_model_name(self.app_label, "OrganizationOwner"),
                "name": "changelist",
                "icon": "ow-org-owner",
            }
        if app_settings.ORGANIZATION_USER_ADMIN:
            items[5] = {
                "label": _("Organization Users"),
                "model": get_model_name(self.app_label, "OrganizationUser"),
                "name": "changelist",
                "icon": "ow-org-user",
            }
        register_menu_group(
            position=40,
            config={
                "label": _("Users & Organizations"),
                "items": items,
                "icon": "ow-user-and-org",
            },
        )

    def set_default_settings(self):
        LOGIN_URL = getattr(settings, "LOGIN_URL", None)
        if not LOGIN_URL:
            setattr(settings, "LOGIN_URL", "account_login")

        LOGOUT_URL = getattr(settings, "LOGOUT_URL", None)
        if not LOGOUT_URL:
            setattr(settings, "LOGOUT_URL", "account_logout")

        if app_settings.USERS_AUTH_API and utils_settings.API_DOCS:
            SWAGGER_SETTINGS = getattr(settings, "SWAGGER_SETTINGS", {})
            SWAGGER_SETTINGS["SECURITY_DEFINITIONS"] = {
                "Bearer": {"type": "apiKey", "in": "header", "name": "Authorization"}
            }
            setattr(settings, "SWAGGER_SETTINGS", SWAGGER_SETTINGS)

        ACCOUNT_ADAPTER = getattr(settings, "ACCOUNT_ADAPTER", None)
        if not ACCOUNT_ADAPTER:
            setattr(
                settings,
                "ACCOUNT_ADAPTER",
                "openwisp_users.accounts.adapter.EmailAdapter",
            )

    def connect_receivers(self):
        OrganizationUser = load_model("openwisp_users", "OrganizationUser")
        OrganizationOwner = load_model("openwisp_users", "OrganizationOwner")
        Organization = load_model("openwisp_users", "Organization")
        signal_tuples = [
            (post_save, "post_save"),
            (post_delete, "post_delete"),
        ]

        pre_save.connect(
            self.handle_org_is_active_change,
            sender=Organization,
            dispatch_uid="handle_org_is_active_change",
        )

        for model in [OrganizationUser, OrganizationOwner]:
            for signal, name in signal_tuples:
                signal.connect(
                    self.update_organizations_dict,
                    sender=model,
                    dispatch_uid="{}_{}_update_organizations_dict".format(
                        name, model.__name__
                    ),
                )
            # If the related user changes, eg: the OrganizationOwner
            # changes from user A to user B, we need to invalidate
            # the cache of user A before the user is changed to user B
            # otherwise the cache of user A will continue claiming
            # that user A is still the owner.
            pre_save.connect(
                self.pre_save_update_organizations_dict,
                sender=model,
                dispatch_uid="{}_{}_pre_save_organizations_dict".format(
                    name, model.__name__
                ),
            )
        post_save.connect(
            self.create_organization_owner,
            sender=OrganizationUser,
            dispatch_uid="make_first_org_user_org_owner",
        )

    @classmethod
    def handle_org_is_active_change(cls, instance, **kwargs):
        if instance._state.adding:
            # If it's a new organization, we don't need to update any cache
            return
        Organization = instance._meta.model
        try:
            old_instance = Organization.objects.only("is_active").get(pk=instance.pk)
        except Organization.DoesNotExist:
            return
        from .tasks import invalidate_org_membership_cache

        if instance.is_active != old_instance.is_active:
            invalidate_org_membership_cache.delay(instance.pk)

    @classmethod
    def pre_save_update_organizations_dict(cls, instance, **kwargs):
        """
        Invalidates user's organizations cache when
        OrganizationUser.user or
        OrganizationOwner.organization_user
        are changed.
        """

        def _invalidate_old_related_obj_cache(instance, check_field):
            Model = instance._meta.model
            try:
                db_obj = Model.objects.select_related(check_field).get(pk=instance.pk)
            except Model.DoesNotExist:
                return
            else:
                if getattr(db_obj, check_field) != getattr(instance, check_field):
                    cls._invalidate_user_cache(getattr(db_obj, check_field))

        if hasattr(instance, "user"):
            _invalidate_old_related_obj_cache(instance, "user")
        else:
            _invalidate_old_related_obj_cache(instance, "organization_user")

    @classmethod
    def _invalidate_user_cache(cls, user):
        User = get_user_model()
        if not isinstance(user, User):
            user = user.user
        # Invalidate the organizations cache of the user
        user._invalidate_user_organizations_dict()

    @classmethod
    def update_organizations_dict(cls, instance, signal, **kwargs):
        if hasattr(instance, "user"):
            user = instance.user
        else:
            user = instance.organization_user.user
        cls._invalidate_user_cache(user)
        # forces caching
        user.organizations_dict

    @classmethod
    def create_organization_owner(cls, instance, created, **kwargs):
        if not created or not instance.is_admin:
            return
        OrganizationOwner = load_model("openwisp_users", "OrganizationOwner")
        org_owner_exist = OrganizationOwner.objects.filter(
            organization=instance.organization
        ).exists()
        if not org_owner_exist:
            with transaction.atomic():
                try:
                    owner = OrganizationOwner(
                        organization_user=instance, organization=instance.organization
                    )
                    owner.full_clean()
                    owner.save()
                except (ValidationError, IntegrityError) as e:
                    logger.exception(
                        f"Got exception {type(e)} while saving "
                        f"OrganizationOwner with organization_user {instance} and "
                        f"organization {instance.organization}"
                    )
