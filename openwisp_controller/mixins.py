from openwisp_users.api.mixins import FilterByOrganizationManaged, FilterByParentManaged
from openwisp_users.api.mixins import ProtectedAPIMixin as BaseProtectedAPIMixin
from openwisp_users.api.permissions import (
    DisabledOrgReadOnly,
    DjangoModelPermissions,
    IsOrganizationManager,
)


class RelatedDeviceModelPermission(DjangoModelPermissions):
    _device_field = "device"

    def _has_permissions(self, request, view, perm, obj=None):
        if request.method in self.READ_ONLY_METHOD:
            return perm
        if obj:
            device = getattr(obj, self._device_field)
        else:
            device = view.get_parent_queryset().first()
        return (
            perm
            and device
            and not device.is_deactivated()
            and (device.organization.is_active or request.method == "DELETE")
        )

    def has_permission(self, request, view):
        perm = super().has_permission(request, view)
        return self._has_permissions(request, view, perm)

    def has_object_permission(self, request, view, obj):
        perm = super().has_object_permission(request, view, obj)
        return self._has_permissions(request, view, perm, obj)


class RelatedDeviceProtectedAPIMixin(FilterByParentManaged, BaseProtectedAPIMixin):
    permission_classes = [
        IsOrganizationManager,
        RelatedDeviceModelPermission,
        DisabledOrgReadOnly,
    ]


class ProtectedAPIMixin(BaseProtectedAPIMixin, FilterByOrganizationManaged):
    pass
