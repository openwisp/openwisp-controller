from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from openwisp_ipam.api import views as ipam_views
from rest_framework.exceptions import ValidationError as DRFValidationError


class SubnetView(ipam_views.SubnetView):
    """Reports in-use subnet division rules at the REST boundary.

    Deleting a subnet cascades to its subnet division rules, which refuse
    the deletion when a device configuration uses them. The refusal is a
    Django ``ValidationError``, which DRF does not translate, so without
    this the request would fail with a server error.
    """

    def perform_destroy(self, instance):
        try:
            # The deletion is wrapped in a transaction so that a refusal
            # rolls it back before the error is reported.
            with transaction.atomic():
                super().perform_destroy(instance)
        except DjangoValidationError as error:
            if getattr(error, "code", None) != "subnet_division_rule_in_use":
                raise
            raise DRFValidationError({"detail": error.messages})


# openwisp_ipam.api.urls.get_api_urls looks up callable views by name.
subnet = SubnetView.as_view()
