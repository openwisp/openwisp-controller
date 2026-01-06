import reversion
from reversion.views import RevisionMixin

from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions, IsOrganizationManager


class RelatedDeviceModelPermission(DjangoModelPermissions):
    _device_field = "device"

    def _has_permissions(self, request, view, perm, obj=None):
        if request.method in self.READ_ONLY_METHOD:
            return perm
        if obj:
            device = getattr(obj, self._device_field)
        else:
            device = view.get_parent_queryset().first()
        return perm and device and not device.is_deactivated()

    def has_permission(self, request, view):
        perm = super().has_permission(request, view)
        return self._has_permissions(request, view, perm)

    def has_object_permission(self, request, view, obj):
        perm = super().has_object_permission(request, view, obj)
        return self._has_permissions(request, view, perm, obj)


class RelatedDeviceProtectedAPIMixin(
    BaseProtectedAPIMixin, FilterByOrganizationManaged
):
    permission_classes = [
        IsOrganizationManager,
        RelatedDeviceModelPermission,
    ]


class ProtectedAPIMixin(BaseProtectedAPIMixin, FilterByOrganizationManaged):
    pass


class AutoRevisionMixin(RevisionMixin):
    revision_atomic = False

    def dispatch(self, request, *args, **kwargs):
        qs = getattr(self, "queryset", None)
        model = getattr(qs, "model", None)
        if (
            request.method in ("POST", "PUT", "PATCH")
            and request.user.is_authenticated
            and model
            and reversion.is_registered(model)
        ):
            with reversion.create_revision(atomic=self.revision_atomic):
                response = super().dispatch(request, *args, **kwargs)
                reversion.set_user(request.user)
                reversion.set_comment(
                    f"API request: {request.method} {request.get_full_path()}"
                )
            return response
        return super().dispatch(request, *args, **kwargs)
