from django_netjsonconfig.controller.generics import (BaseChecksumView,
                                                      BaseDownloadConfigView,
                                                      BaseRegisterView,
                                                      BaseReportStatusView)
from django_netjsonconfig.utils import invalid_response

from ..models import Config, OrganizationConfigSettings


class ActiveOrgMixin(object):
    """
    adds check to organization.is_active to ``get_object`` method
    """
    def get_object(self, *args, **kwargs):
        kwargs['organization__is_active'] = True
        return super(ActiveOrgMixin, self).get_object(*args, **kwargs)


class ChecksumView(ActiveOrgMixin, BaseChecksumView):
    model = Config


class DownloadConfigView(ActiveOrgMixin, BaseDownloadConfigView):
    model = Config


class ReportStatusView(ActiveOrgMixin, BaseReportStatusView):
    model = Config


class RegisterView(BaseRegisterView):
    model = Config

    def forbidden(self, request):
        """
        ensures request is authorized:
            - secret matches an organization's shared_secret
            - the organization has registration_enabled set to True
        """
        try:
            secret = request.POST.get('secret')
            org_settings = OrganizationConfigSettings.objects \
                                                     .select_related('organization') \
                                                     .get(shared_secret=secret,
                                                          organization__is_active=True)
        except OrganizationConfigSettings.DoesNotExist:
            return invalid_response(request, 'unrecognized secret', status=403)
        if not org_settings.registration_enabled:
            return invalid_response(request, 'registration disabled', status=403)
        # set an organization attribute as a side effect
        # this attribute will be used in ``init_object``
        self.organization = org_settings.organization

    def init_object(self, **kwargs):
        kwargs['organization'] = self.organization
        return super(RegisterView, self).init_object(**kwargs)


checksum = ChecksumView.as_view()
download_config = DownloadConfigView.as_view()
report_status = ReportStatusView.as_view()
register = RegisterView.as_view()
