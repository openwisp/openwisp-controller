from openwisp_controller.config.admin import (
    DeviceAdmin,
    DeviceGroupAdmin,
    TemplateAdmin,
    VpnAdmin,
)

# Monkey Patching done only for testing purposes
DeviceAdmin.fields += ['details']
TemplateAdmin.fields += ['details']
VpnAdmin.fields += ['details']
DeviceGroupAdmin.fields += ['details']
