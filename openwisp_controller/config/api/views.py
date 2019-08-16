from django_netjsonconfig.api.generics import (BaseSubscriptionCountView, BaseTemplateDetailView,
                                               BaseTemplateSubscriptionView, BaseTemplateSynchronizationView)
from django_netjsonconfig.api.serializers import ListSubscriptionCountSerializer

from openwisp_users.models import Organization, OrganizationUser

from ...pki.models import Ca, Cert
from ..models import Template, TemplateSubscription, Vpn
from .generics import BaseListCreateTemplateView
from .serializers import (CaOrgSerializer, CertOrgSerializer, ListOrgTemplateSerializer,
                          TemplateDetailOrgSerializer, VpnOrgSerializer)


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


class ListTemplateView(BaseListCreateTemplateView):
    queryset = Template.objects.all()
    template_model = Template
    list_serializer = ListOrgTemplateSerializer
    template_subscription_model = TemplateSubscription
    vpn_model = Vpn
    ca_model = Ca
    cert_model = Cert
    org_model = Organization
    org_user_model = OrganizationUser
    ca_serializer = CaOrgSerializer
    cert_serializer = CertOrgSerializer
    vpn_serializer = VpnOrgSerializer
    template_serializer = TemplateDetailOrgSerializer
    list_template_serializer = ListOrgTemplateSerializer

    def get_queryset(self):
        """
        If organization is given, return templates belonging to that
        organization otherwise return an empty
        queryset.
        """
        org_name = self.request.GET.get('org', None)
        queryset = super(BaseListCreateTemplateView, self).get_queryset()
        if org_name:
            try:
                org = Organization.objects.get(name=org_name)
            except Organization.DoesNotExist:
                return queryset
            queryset = queryset.filter(organization=org)
            return queryset
        else:
            return queryset


class TemplateSubscriptionView(BaseTemplateSubscriptionView):
    template_subscription_model = TemplateSubscription
    template_model = Template


class TemplateSynchronizationView(BaseTemplateSynchronizationView):
    template_model = Template
    template_subscription_model = TemplateSubscription


class SubscriptionCountView(BaseSubscriptionCountView):
    template_subscription_model = TemplateSubscription
    subscription_serializer = ListSubscriptionCountSerializer


template_detail = TemplateDetailView.as_view()
list_template = ListTemplateView.as_view()
subscribe_template = TemplateSubscriptionView.as_view()
synchronize_template = TemplateSynchronizationView.as_view()
subscription_count = SubscriptionCountView.as_view()
