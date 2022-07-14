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
device_registered = Signal()
device_registered.__doc__ = """
Providing arguments: ['instance', 'is_new']
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
vpn_server_modified = Signal()
vpn_server_modified.__doc__ = """
providing arguments: ['instance']
"""
