from django.dispatch import Signal

checksum_requested = Signal(providing_args=['instance', 'request'])
config_download_requested = Signal(providing_args=['instance', 'request'])
config_status_changed = Signal(providing_args=['instance'])
# device and config args are maintained for backward compatibility
config_modified = Signal(providing_args=['instance', 'device', 'config'])
