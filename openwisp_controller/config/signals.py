from django.dispatch import Signal

checksum_requested = Signal(providing_args=['instance', 'request'])
config_download_requested = Signal(providing_args=['instance', 'request'])
config_status_changed = Signal(providing_args=['instance'])
# device and config args are maintained for backward compatibility
config_modified = Signal(
    providing_args=['instance', 'device', 'config', 'previous_status', 'action']
)
device_registered = Signal(providing_args=['instance', 'is_new'])
management_ip_changed = Signal(
    providing_args=['instance', 'management_ip', 'old_management_ip']
)
device_name_changed = Signal(providing_args=['instance'])
device_group_changed = Signal(providing_args=['instance', 'group', 'old_group'])
