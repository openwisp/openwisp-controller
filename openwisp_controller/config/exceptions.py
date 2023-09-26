from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class OrganizationDeviceLimitExceeded(ValidationError):
    """
    Raised when the registered devices exceeds configured
    device limit for an organization.
    """

    error_message = _(
        'The specified limit is lower than the amount of'
        ' devices currently held by this organization.'
        ' Please remove some devices or consider increasing'
        ' the device limit.'
    )

    def __init__(self):
        error = {'device_limit': [self.error_message]}
        super().__init__(error, code=None, params=None)


class ZeroTierIdentityGenerationError(Exception):
    pass
