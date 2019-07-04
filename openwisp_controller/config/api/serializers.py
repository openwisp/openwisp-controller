from django_netjsonconfig.api.serializers import (CaSerializer, CertSerializer, ListTemplateSerializer,
                                                  TemplateDetailSerializer, VpnSerializer)
from rest_framework import serializers

from openwisp_users.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        exclude = ('users',)


class VpnOrgSerializer(VpnSerializer):
    pass


class TemplateDetailOrgSerializer(TemplateDetailSerializer):
    """
    Openwisp-controller template detail serializer
    """
    organization = OrganizationSerializer(read_only=True)


class CaOrgSerializer(CaSerializer):
    """
    Openwisp-controller Ca serializer
    """
    pass


class CertOrgSerializer(CertSerializer):
    """
    openwisp-controller Cert serializer
    """
    pass


class ListOrgTemplateSerializer(ListTemplateSerializer):
    """
    openwisp-controller list template serializer
    """
    pass
