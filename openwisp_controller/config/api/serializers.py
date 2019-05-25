from rest_framework import serializers

from openwisp_users.models import Organization

from ...config.models import Template, Vpn
from ...pki.models import Ca, Cert


class CaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ca
        fields = "__all__"


class CertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cert
        fields = "__all__"


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = "__all__"


class VpnSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    ca = CaSerializer(read_only=True)
    cert = CertSerializer(read_only=True)

    class Meta:
        model = Vpn
        fields = "__all__"


class TemplateRetrieveSerializer(serializers.ModelSerializer):
    vpn = VpnSerializer(read_only=True)

    class Meta:
        model = Template
        fields = ('id', 'type', 'default_values', 'key', 'auto_cert',
                  'backend', 'vpn', 'url', 'config')
