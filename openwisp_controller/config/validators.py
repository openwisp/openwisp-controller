from django.core.validators import RegexValidator, _lazy_re_compile
from django.utils.translation import gettext_lazy as _

key_validator = RegexValidator(
    _lazy_re_compile('^[^\s/\.]+$'),
    message=_('Key must not contain spaces, dots or slashes.'),
    code='invalid',
)

mac_address_regex = '^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
mac_address_validator = RegexValidator(
    _lazy_re_compile(mac_address_regex),
    message=_('Must be a valid mac address.'),
    code='invalid',
)

# device name must either be a hostname or a valid mac address
hostname_regex = (
    '^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}'
    '[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9]'
    '[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$'
)
device_name_validator = RegexValidator(
    _lazy_re_compile('{0}|{1}'.format(hostname_regex, mac_address_regex)),
    message=_('Must be either a valid hostname or mac address.'),
    code='invalid',
)
