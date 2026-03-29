from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework import pagination
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    get_object_or_404,
)
from rest_framework.mixins import UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from swapper import load_model

from openwisp_users.api.permissions import DjangoModelPermissions

from .mixins import FilterByParent
from .mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from .serializers import (
    ChangePasswordSerializer,
    EmailAddressSerializer,
    GroupSerializer,
    OrganizationDetailSerializer,
    OrganizationSerializer,
    SuperUserDetailSerializer,
    SuperUserListSerializer,
    UserDetailSerializer,
    UserListSerializer,
)
from .swagger import ObtainTokenRequest, ObtainTokenResponse
from .throttling import AuthRateThrottle

Group = load_model("openwisp_users", "Group")
Organization = load_model("openwisp_users", "Organization")
User = get_user_model()
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


class ProtectedAPIMixin(BaseProtectedAPIMixin):
    permission_classes = (
        IsAuthenticated,
        DjangoModelPermissions,
    )


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ObtainAuthTokenView(ObtainAuthToken):
    throttle_classes = [AuthRateThrottle]
    authentication_classes = []
    renderer_classes = api_settings.DEFAULT_RENDERER_CLASSES
    metadata_class = api_settings.DEFAULT_METADATA_CLASS
    versioning_class = api_settings.DEFAULT_VERSIONING_CLASS

    @swagger_auto_schema(
        request_body=ObtainTokenRequest, responses={200: ObtainTokenResponse}
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class BaseOrganizationView(ProtectedAPIMixin):
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Organization.objects.order_by("-created")
        if user.is_anonymous:
            return
        return Organization.objects.filter(pk__in=user.organizations_managed).order_by(
            "-created"
        )


class OrganizationListCreateView(BaseOrganizationView, ListCreateAPIView):
    pagination_class = ListViewPagination


class OrganizationDetailView(BaseOrganizationView, RetrieveUpdateDestroyAPIView):
    serializer_class = OrganizationDetailSerializer


class BaseUserView(ProtectedAPIMixin):
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return User.objects.order_by("-date_joined")

        if not user.is_superuser and not user.is_anonymous:
            org_users = OrganizationUser.objects.filter(user=user).select_related(
                "organization"
            )
            qs = User.objects.none()
            for org_user in org_users:
                if org_user.is_admin:
                    qs = qs | org_user.organization.users.all().distinct()
            qs = qs.filter(is_superuser=False)
            return qs.order_by("-date_joined")


class UsersListCreateView(BaseUserView, ListCreateAPIView):
    pagination_class = ListViewPagination

    def get_serializer_class(self):
        user = self.request.user
        if user.is_superuser:
            return SuperUserListSerializer
        return UserListSerializer


class UserDetailView(BaseUserView, RetrieveUpdateDestroyAPIView):
    def get_serializer_class(self):
        user = self.request.user
        if user.is_superuser:
            return SuperUserDetailSerializer
        return UserDetailSerializer


class GroupListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    queryset = Group.objects.prefetch_related(
        "permissions", "permissions__content_type"
    ).order_by("name")
    serializer_class = GroupSerializer
    pagination_class = ListViewPagination


class GroupDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    queryset = Group.objects.prefetch_related(
        "permissions", "permissions__content_type"
    ).order_by("name")
    serializer_class = GroupSerializer


class UpdateAPIView(UpdateModelMixin, GenericAPIView):
    """
    Concrete view for updating a model instance.
    """

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class ChangePasswordView(BaseUserView, UpdateAPIView):
    serializer_class = ChangePasswordSerializer

    def get_permissions(self):
        """
        Remove `DangoModelPermissions` permission
        class if loggedin user wants to change
        his own password.
        """
        if str(self.request.user.id) == self.kwargs["pk"]:
            self.permission_classes = [IsAuthenticated]
        else:
            self.permission_classes = [IsAuthenticated, DjangoModelPermissions]
        return super(self.__class__, self).get_permissions()

    def get_object(self):
        if getattr(self, "swagger_fake_view", False):
            # To get rid of assertion error raised in
            # the dev server, and for schema generation
            return User.objects.none()

        user = User.objects.filter(id=self.request.user.id)
        qs = self.get_queryset()
        if (
            user.first().is_staff is True
            and not qs.filter(pk=self.request.user.id).exists()
        ):
            qs = qs | user
        filter_kwargs = {
            "id": self.kwargs["pk"],
        }
        obj = get_object_or_404(qs, **filter_kwargs)
        return obj

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.get_object()
        return context

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"status": "Success", "message": _("Password updated successfully")}
        )


class BaseEmailView(ProtectedAPIMixin, FilterByParent, GenericAPIView):
    model = EmailAddress
    serializer_class = EmailAddressSerializer

    def get_queryset(self):
        return EmailAddress.objects.select_related("user").order_by("id")

    def initial(self, *args, **kwargs):
        super().initial(*args, **kwargs)
        self.assert_parent_exists()

    def get_parent_queryset(self):
        qs = User.objects.filter(pk=self.kwargs["pk"])
        if self.request.user.is_superuser:
            return qs
        return self.get_organization_queryset(qs)

    def get_organization_queryset(self, qs):
        orgs = self.request.user.organizations_managed
        app_label = User._meta.app_config.label
        filter_kwargs = {
            # exclude superusers
            "is_superuser": False,
            # ensure user is member of the org
            f"{app_label}_organizationuser__organization_id__in": orgs,
        }
        return qs.filter(**filter_kwargs).distinct()

    def get_serializer_context(self):
        if getattr(self, "swagger_fake_view", False):
            # To get rid of assertion error raised in
            # the dev server, and for schema generation
            return None
        context = super().get_serializer_context()
        context["user"] = self.get_parent_queryset().first()
        return context


class EmailListCreateView(BaseEmailView, ListCreateAPIView):
    pagination_class = ListViewPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # To get rid of assertion error raised in
            # the dev server, and for schema generation
            return EmailAddress.objects.none()
        return super().get_queryset().filter(user_id=self.kwargs["pk"])


class EmailUpdateView(BaseEmailView, RetrieveUpdateDestroyAPIView):
    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        queryset = queryset.filter(user=self.get_parent_queryset().first())
        filter_kwargs = {
            "id": self.kwargs["email_id"],
        }
        obj = get_object_or_404(queryset, **filter_kwargs)
        self.check_object_permissions(self.request, obj)
        return obj


obtain_auth_token = ObtainAuthTokenView.as_view()
organization_list = OrganizationListCreateView.as_view()
organization_detail = OrganizationDetailView.as_view()
user_list = UsersListCreateView.as_view()
user_detail = UserDetailView.as_view()
group_list = GroupListCreateView.as_view()
group_detail = GroupDetailView.as_view()
change_password = ChangePasswordView.as_view()
email_update = EmailUpdateView.as_view()
email_list = EmailListCreateView.as_view()
