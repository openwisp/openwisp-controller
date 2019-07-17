from django_netjsonconfig.api.generics import BaseListTemplateView, BaseTemplateDetailView

from openwisp_users.models import Organization

from ...pki.models import Ca, Cert
from ..models import Template, Vpn
from .serializers import (CaOrgSerializer, CertOrgSerializer, ListOrgTemplateSerializer,
                          TemplateDetailOrgSerializer, VpnOrgSerializer)


class TemplateDetailView(BaseTemplateDetailView):
    # Dynamically set the serializer models
    template_model = Template
    vpn_model = Vpn
    ca_model = Ca
    cert_model = Cert
    # Specify serializers to be used in base views.
    ca_serializer = CaOrgSerializer
    cert_serializer = CertOrgSerializer
    vpn_serializer = VpnOrgSerializer
    template_detail_serializer = TemplateDetailOrgSerializer
    queryset = Template.objects.none()


class ListTemplateView(BaseListTemplateView):
    queryset = Template.objects.all()
    template_model = Template
    list_serializer = ListOrgTemplateSerializer

    def get_queryset(self):
        """
        If organization is given, return templates belonging to that
        organization otherwise return an empty
        queryset.
        """
        org_name = self.request.GET.get('org', None)
        queryset = super(ListTemplateView, self).get_queryset()
        if org_name:
            try:
                org = Organization.objects.get(name=org_name)
            except Organization.DoesNotExist:
                return self.template_model.objects.none()
            queryset = queryset.filter(organization=org)
            return queryset
        else:
            qs = self.template_model.objects.none()
            return qs


template_detail = TemplateDetailView.as_view()
list_template = ListTemplateView.as_view()
