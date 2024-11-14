from django.dispatch import Signal

checksum_requested = Signal()
checksum_requested.__doc__ = """
Providing arguments: ['instance', 'request']
"""
config_download_requested = Signal()
config_download_requested.__doc__ = """
Providing arguments: ['instance', 'request']
"""
config_status_changed = Signal()
config_status_changed.__doc__ = """
Providing arguments: ['instance']
"""
# device and config args are maintained for backward compatibility
config_modified = Signal()
config_modified.__doc__ = """
Providing arguments: ['instance', 'device', 'config', 'previous_status', 'action']
"""
config_deactivated = Signal()
config_deactivated.__doc__ = """
Providing arguments: ['instance', 'previous_status']
"""
config_deactivating = Signal()
config_deactivating.__doc__ = """
Providing arguments: ['instance', 'previous_status']
"""
device_registered = Signal()
device_registered.__doc__ = """
Providing arguments: ['instance', 'is_new']
"""
device_deactivated = Signal()
device_deactivated.__doc__ = """
Providing arguments: ['instance']
"""
device_activated = Signal()
device_activated.__doc__ = """
Providing arguments: ['instance']
"""
management_ip_changed = Signal()
management_ip_changed.__doc__ = """
Providing arguments: ['instance', 'management_ip', 'old_management_ip']
"""
device_name_changed = Signal()
device_name_changed.__doc__ = """
Providing arguments: ['instance']
"""
device_group_changed = Signal()
device_group_changed.__doc__ = """
Providing arguments: ['instance']
"""
vpn_peers_changed = Signal()
vpn_peers_changed.__doc__ = """
providing arguments: ['instance']
"""
group_templates_changed = Signal()
group_templates_changed.__doc__ = """
providing arguments: ['instance', 'templates', 'old_templates']
"""
config_backend_changed = Signal()
config_backend_changed.__doc__ = """
providing arguments: ['instance', 'backend', 'old_backend']
"""
vpn_server_modified = Signal()
vpn_server_modified.__doc__ = """
providing arguments: ['instance']
"""
