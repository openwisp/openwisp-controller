from django.core.validators import RegexValidator, _lazy_re_compile
from django.utils.translation import gettext_lazy as _

key_validator = RegexValidator(
    _lazy_re_compile("^[^\\s/\\.]+$"),
    message=_("This value must not contain spaces, dots or slashes."),
    code="invalid",
)
