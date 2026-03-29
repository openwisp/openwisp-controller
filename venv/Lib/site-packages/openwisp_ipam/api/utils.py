import swapper
from django.utils.translation import gettext_lazy as _
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied

from openwisp_ipam.base.models import CsvImportException

Organization = swapper.load_model("openwisp_users", "Organization")


class CsvImportAPIException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class AuthorizeCSVImport:
    def assert_organization_permissions(self, request):
        if request.user.is_superuser:
            return
        try:
            organization = self.get_csv_organization(request)
            if organization is None or str(
                organization.pk
            ) in self.get_user_organizations(request):
                return
        except CsvImportException as e:
            raise CsvImportAPIException(str(e))
        except IndexError:
            raise CsvImportAPIException(_("Invalid data format"))
        raise PermissionDenied(
            _("You do not have permission to import data into this organization")
        )

    def get_csv_organization(self):
        raise NotImplementedError()

    def get_user_organizations(self):
        raise NotImplementedError()


class AuthorizeCSVOrgManaged(AuthorizeCSVImport):
    def get_user_organizations(self, request):
        return request.user.organizations_managed
