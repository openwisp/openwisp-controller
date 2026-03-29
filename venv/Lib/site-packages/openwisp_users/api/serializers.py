import logging

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from swapper import load_model

from openwisp_utils.api.serializers import ValidatedModelSerializer

Group = load_model("openwisp_users", "Group")
Organization = load_model("openwisp_users", "Organization")
User = get_user_model()
OrganizationUser = load_model("openwisp_users", "OrganizationUser")
logger = logging.getLogger(__name__)
OrganizationOwner = load_model("openwisp_users", "OrganizationOwner")


class OrganizationSerializer(ValidatedModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "is_active",
            "slug",
            "description",
            "email",
            "url",
            "created",
            "modified",
        )
        # This allows replacing the default "UniqueValidator" for
        # the slug field with the custom validation defined below.
        extra_kwargs = {"slug": {"validators": []}}

    def validate(self, data):
        """
        Custom validation error if an organization
        already exists with the given slug.
        """
        org = Organization.objects.filter(slug__exact=data.get("slug")).first()
        if org:
            raise serializers.ValidationError(
                {
                    "slug": _("organization with this slug already exists."),
                    "organization": org.pk,
                }
            )
        return super().validate(data)


class CustomPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def display_value(self, instance):
        return instance.user.username

    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            queryset = OrganizationUser.objects.all()
        else:
            queryset = OrganizationUser.objects.filter(
                Q(organization__in=user.organizations_managed)
            )
        return queryset.select_related()


class OrganizationOwnerSerializer(serializers.ModelSerializer):
    organization_user = CustomPrimaryKeyRelatedField(allow_null=True)

    class Meta:
        model = OrganizationOwner
        fields = ("organization_user",)
        extra_kwargs = {"organization_user": {"allow_null": True}}


class OrganizationDetailSerializer(serializers.ModelSerializer):
    owner = OrganizationOwnerSerializer(required=False)

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "is_active",
            "slug",
            "description",
            "email",
            "url",
            "owner",
            "created",
            "modified",
        )

    def update(self, instance, validated_data):
        if validated_data.get("owner"):
            org_owner = validated_data.pop("owner")
            existing_owner = OrganizationOwner.objects.filter(organization=instance)

            if (
                existing_owner.exists() is False
                and org_owner["organization_user"] is not None
            ):
                org_user = org_owner.get("organization_user")
                with transaction.atomic():
                    org_owner = OrganizationOwner.objects.create(
                        organization=instance, organization_user=org_user
                    )
                    org_owner.full_clean()
                    org_owner.save()
                return super().update(instance, validated_data)

            if existing_owner.exists():
                if org_owner["organization_user"] is None:
                    existing_owner.first().delete()
                    return super().update(instance, validated_data)

                existing_owner_user = existing_owner[0].organization_user
                if org_owner.get("organization_user") != existing_owner_user:
                    org_user = org_owner.get("organization_user")
                    with transaction.atomic():
                        existing_owner.first().delete()
                        org_owner = OrganizationOwner.objects.create(
                            organization=instance, organization_user=org_user
                        )
                        org_owner.full_clean()
                        org_owner.save()

        instance = self.instance or self.Meta.model(**validated_data)
        instance.full_clean()
        return super().update(instance, validated_data)


class MyPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_representation(self, value):
        return f"{value.pk}: {value.natural_key()[2]} | {value.name}"

    def to_internal_value(self, value):
        if type(value) is int:
            return value
        return int(value.partition(":")[0])


class GroupSerializer(serializers.ModelSerializer):
    permissions = MyPrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.select_related("content_type"),
        required=False,
    )

    class Meta:
        model = Group
        fields = ("id", "name", "permissions")

    def create(self, validated_data):
        permissions = validated_data.pop("permissions")
        instance = self.instance or self.Meta.model(**validated_data)
        instance.full_clean()
        instance.save()
        instance.permissions.add(*permissions)
        return instance

    def update(self, instance, validated_data):
        if "permissions" in validated_data:
            permissions = validated_data.pop("permissions")
            instance.permissions.clear()
            instance.permissions.add(*permissions)
        instance.full_clean()
        return super().update(instance, validated_data)


class OrgUserCustomPrimarykeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        user = self.context["request"].user
        if user.is_superuser:
            queryset = Organization.objects.all()
        else:
            queryset = Organization.objects.filter(pk__in=user.organizations_managed)
        return queryset


class OrganizationUserSerializer(serializers.ModelSerializer):
    organization = OrgUserCustomPrimarykeyRelatedField(allow_null=True)

    class Meta:
        model = OrganizationUser
        fields = (
            "is_admin",
            "organization",
        )

    def to_internal_value(self, data):
        if type(data) is list:
            if data == []:
                data = dict()
            else:
                data = data[0]
        return super().to_internal_value(data)


class BaseSuperUserSerializer(serializers.ModelSerializer):
    organization_users = OrganizationUserSerializer(required=False)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        org_users = OrganizationUser.objects.filter(user=instance).select_related()
        list_of_org_users = []
        for org_user in org_users:
            user = dict()
            user["is_admin"] = org_user.is_admin
            user["organization"] = org_user.organization.id
            list_of_org_users.append(user)
        data["organization_users"] = list_of_org_users
        return data


class SuperUserListSerializer(BaseSuperUserSerializer):
    email_verified = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "email_verified",
            "password",
            "first_name",
            "last_name",
            "phone_number",
            "birth_date",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
            "organization_users",
        )
        read_only_fields = ("last_login", "date_joined")
        extra_kwargs = {
            "email": {"required": True},
            "password": {"write_only": True, "style": {"input_type": "password"}},
        }

    def validate_email(self, value):
        if not value:
            raise serializers.ValidationError(_("This field cannot be blank."))
        return value

    def create(self, validated_data):
        group_data = validated_data.pop("groups", None)
        org_user_data = validated_data.pop("organization_users", None)
        password = validated_data.pop("password")
        email_verified = validated_data.pop("email_verified", False)

        instance = self.instance or self.Meta.model(**validated_data)
        instance.set_password(password)
        instance.full_clean()
        instance.save()

        if group_data:
            instance.groups.add(*group_data)

        if org_user_data:
            if org_user_data.get("organization") is not None:
                org_user_data["user"] = instance
                org_user_instance = OrganizationUser(**org_user_data)
                org_user_instance.full_clean()
                org_user_instance.save()

        if instance.email:
            try:
                email = EmailAddress.objects.add_email(
                    self.context["request"],
                    user=instance,
                    email=instance.email,
                    confirm=not email_verified,
                    signup=True,
                )
                if email_verified:
                    email.primary = True
                    email.verified = True
                    email.save(update_fields=["primary", "verified"])
            except Exception as e:
                logger.exception(
                    "Got exception {} while sending "
                    "verification email to user {}, email {}".format(
                        type(e), instance.username, instance.email
                    )
                )

        return instance


class SuperUserDetailSerializer(BaseSuperUserSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "bio",
            "url",
            "company",
            "location",
            "phone_number",
            "birth_date",
            "notes",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "date_joined",
            "groups",
            "user_permissions",
            "organization_users",
        )
        extra_kwargs = {
            "last_login": {"read_only": True},
            "date_joined": {"read_only": True},
        }

    def update(self, instance, validated_data):
        org_user_data = dict()
        if validated_data.get("organization_users"):
            org_user_data = validated_data.pop("organization_users")

        if org_user_data.get("organization") is not None:
            org_user = None
            try:
                org_user = OrganizationUser.objects.get(
                    user=instance, organization=org_user_data["organization"]
                )
            except OrganizationUser.DoesNotExist:
                pass
            if org_user:
                if (
                    str(org_user_data["organization"].id)
                    in instance.organizations_dict.keys()
                ):
                    if org_user.is_admin != org_user_data.get("is_admin"):
                        org_user.is_admin = org_user_data["is_admin"]
                        org_user.full_clean()
                        org_user.save()
                    else:
                        org_user.delete()
            else:
                org_user_data["user"] = instance
                org_user_instance = OrganizationUser(**org_user_data)
                org_user_instance.full_clean()
                org_user_instance.save()

        instance = self.instance or self.Meta.model(**validated_data)
        instance.full_clean()
        return super().update(instance, validated_data)


def get_userlist_fields(fields):
    """
    Returns the fields for `UserListSerializer`.
    """
    fields = list(fields)
    fields.remove("is_superuser")
    fields = tuple(fields)
    return fields


class UserListSerializer(SuperUserListSerializer):
    class Meta:
        model = User
        fields = get_userlist_fields(SuperUserListSerializer.Meta.fields[:])
        read_only_fields = ("last_login", "date_joined")
        extra_kwargs = {
            "email": {"required": True},
            "password": {"write_only": True, "style": {"input_type": "password"}},
        }


def get_userdetail_fields(fields):
    """
    Returns the fields for `UserDetailSerializer`.
    """
    fields = list(fields)
    fields.remove("is_superuser")
    fields.remove("user_permissions")
    fields = tuple(fields)
    return fields


class UserDetailSerializer(SuperUserDetailSerializer):
    organization_users = OrganizationUserSerializer(required=False, read_only=True)

    class Meta:
        model = User
        fields = get_userdetail_fields(SuperUserDetailSerializer.Meta.fields[:])
        extra_kwargs = {
            "last_login": {"read_only": True},
            "date_joined": {"read_only": True},
        }


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        allow_null=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate_confirm_password(self, value):
        if self.initial_data.get("new_password") != self.initial_data.get(
            "confirm_password"
        ):
            raise serializers.ValidationError(
                _("The two password fields didn’t match.")
            )
        return value

    def validate_current_password(self, value):
        logged_user = self.context["request"].user
        if logged_user.is_superuser:
            return value
        elif logged_user.organizations_managed:
            return value
        else:
            if self.initial_data.get("new_password"):
                to_change_user = self.context["user"]
                if not to_change_user.check_password(value):
                    raise serializers.ValidationError(
                        _(
                            "Your old password was entered incorrectly."
                            " Please enter it again."
                        )
                    )
        return value

    def validate_new_password(self, value):
        if self.initial_data.get("current_password") == self.initial_data.get(
            "new_password"
        ):
            raise serializers.ValidationError(
                _("New password cannot be the same as your old password.")
            )
        return value

    def save(self, **kwargs):
        password = self.validated_data["new_password"]
        user = self.context["user"]
        user.set_password(password)
        user.save()


class EmailAddressSerializer(ValidatedModelSerializer):
    class Meta:
        model = EmailAddress
        fields = ("id", "email", "verified", "primary")
        extra_kwargs = {"verified": {"read_only": True}}

    def validate(self, data):
        data["user"] = self.context["user"]
        return super().validate(data)
