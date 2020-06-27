from openwisp_controller.config.admin import DeviceAdmin, TemplateAdmin, VpnAdmin

# Monkey Patching done only for testing purposes
DeviceAdmin.fields += ['details']
TemplateAdmin.fieldsets[0][1]['fields'].append('details')
VpnAdmin.fields += ['details']
