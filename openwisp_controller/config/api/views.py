from django_netjsonconfig.api.generics import (BaseListTemplateView, BaseTemplateDetailView,
                                               BaseTemplateSubscriptionView, BaseTemplateSynchronizationView)

from openwisp_users.models import Organization

from ...pki.models import Ca, Cert
from ..models import Template, TemplateSubscription, Vpn
from .generics import BaseListCreateTemplateView
from .serializers import (CaOrgSerializer, CertOrgSerializer, ListCreateTemplateSerializer,
                          ListOrgTemplateSerializer, TemplateDetailOrgSerializer, VpnOrgSerializer)


class TemplateDetailView(BaseTemplateDetailView):
    # Dynamically set serializer models
    template_model = Template
    vpn_model = Vpn
    ca_model = Ca
    cert_model = Cert
    # Specify serializers to be used in base view.
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


class ListCreateTemplateView(BaseListCreateTemplateView):
    ListCreateTemplateSerializer.Meta.model = Template
    CaOrgSerializer.Meta.model = Ca
    CertOrgSerializer.Meta.model = Cert
    VpnOrgSerializer.Meta.model = Vpn
    serializer_class = ListCreateTemplateSerializer


class TemplateSubscriptionView(BaseTemplateSubscriptionView):
    template_subscribe_model = TemplateSubscription
    template_model = Template


class TemplateSynchronizationView(BaseTemplateSynchronizationView):
    template_model = Template


template_detail = TemplateDetailView.as_view()
list_template = ListTemplateView.as_view()
create_template = ListCreateTemplateView.as_view()
notify_template = TemplateSubscriptionView.as_view()
synchronize_template = TemplateSynchronizationView.as_view()
