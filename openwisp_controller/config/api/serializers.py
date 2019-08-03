from django_netjsonconfig.api.serializers import (CaSerializer, CertSerializer, ListTemplateSerializer,
                                                  TemplateDetailSerializer, VpnSerializer)
from django_netjsonconfig.utils import create_update_object
from rest_framework import serializers

from openwisp_users.models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        exclude = ('users', 'created', 'modified')


class CaOrgSerializer(CaSerializer):
    """
    Openwisp-controller Ca serializer
    """
    organization = OrganizationSerializer()

    def create(self, validated_data):
        return create_update_object(self.Meta.model, validated_data)

    def to_internal_value(self, value):
        """
        Convert extensions back to its default format
        """
        return value


class CertOrgSerializer(CertSerializer):
    """
    openwisp-controller Cert serializer
    """
    organization = OrganizationSerializer()
    ca = CaOrgSerializer()

    def create(self, validated_data):
        return create_update_object(self.Meta.model, validated_data)

    def to_internal_value(self, value):
        """
        Convert extensions back to its default format
        """
        return value


class VpnOrgSerializer(VpnSerializer):
    """
    Openwisp-controller vpn serializer
    """
    organization = OrganizationSerializer()
    ca = CaOrgSerializer()
    cert = CertOrgSerializer()

    def create(self, validated_data):
        return create_update_object(self.Meta.model, validated_data)

    def to_internal_value(self, value):
        """
        Convert Config back to its default format
        """
        return value


class TemplateDetailOrgSerializer(TemplateDetailSerializer):
    """
    Openwisp-controller template detail serializer
    """
    organization = OrganizationSerializer()
    vpn = VpnOrgSerializer()

    def create(self, validated_data):
        return create_update_object(self.Meta.model, validated_data)

    def to_internal_value(self, value):
        """
        Convert Config back to its default format
        """
        return value


class ListOrgTemplateSerializer(ListTemplateSerializer):
    """
    openwisp-controller list template serializer
    """
