from openwisp_controller.config.admin import DeviceAdmin, TemplateAdmin, VpnAdmin

# Monkey Patching done only for testing purposes
DeviceAdmin.fields += ['details']
TemplateAdmin.fields += ['details']
VpnAdmin.fields += ['details']
