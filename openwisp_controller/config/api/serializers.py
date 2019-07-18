from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils.translation import gettext_lazy as _
from django_netjsonconfig.api.serializers import (CaSerializer, CertSerializer, ListTemplateSerializer,
                                                  TemplateDetailSerializer, VpnSerializer)
from rest_framework import serializers

from openwisp_users.models import Organization

from ...pki.models import Ca, Cert
from ..models import Template, Vpn


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


class ListCreateTemplateSerializer(TemplateDetailSerializer, serializers.Field):
    """
    Serializer to list and create templates for authenticated users.
    """
    organization = OrganizationSerializer(read_only=True)

    # Stores organizations for authenticated user.
    user_orgs = None

    def to_internal_value(self, value):
        """
        Convert Config back to its default format
        """
        return value

    def create(self, validated_data):
        vpn = validated_data.get('vpn', None)
        if vpn:
            ca = vpn.get('ca', None)
            cert = vpn.get('cert', None)
            ca_instance = self._get_object(Ca, **ca)
            cert['ca'] = ca_instance
            cert_instance = self._get_object(Cert, **cert)
            vpn['ca'] = ca_instance
            vpn['cert'] = cert_instance
            vpn_instance = self._get_object(Vpn, **vpn)
            validated_data['vpn'] = vpn_instance
        template = self._get_object(Template, **validated_data)
        return template

    def _get_object(self, model, **data):
        """
        Get objects with specified data from model
        """
        try:
            obj = model.objects.get(name=data['name'],
                                    organization__in=self.user_orgs)
            if model.__name__ == 'Template':
                raise ValidationError(_('A template with name {0} already exist'.format(obj.name)))
        except model.DoesNotExist:
            obj = model(**data)
            try:
                obj.save()
            except IntegrityError as e:
                raise ValidationError(_(str(e)))
        return obj
