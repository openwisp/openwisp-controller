from openwisp_users.api.mixins import FilterByOrganizationManaged
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import DjangoModelPermissions, IsOrganizationManager


class RelatedDeviceModelPermission(DjangoModelPermissions):
    _device_field = 'device'

    def _has_permissions(self, request, view, perm, obj=None):
        if request.method in self.READ_ONLY_METHOD:
            return perm
        if obj:
            device = getattr(obj, self._device_field)
        else:
            device = view.get_parent_queryset()[0]
        return perm and not device.is_deactivated()

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
