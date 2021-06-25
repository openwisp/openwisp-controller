from django.utils.translation import ugettext_lazy as _
from django_x509.base.models import (
    default_ca_validity_end,
    default_cert_validity_end,
    default_validity_start,
)
from rest_framework import serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass


class CaListSerializer(BaseSerializer):

    extensions = serializers.JSONField(
        initial=[],
        help_text=_('additional x509 certificate extensions'),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Ca
        fields = [
            'id',
            'name',
            'organization',
            'notes',
            'key_length',
            'digest',
            'validity_start',
            'validity_end',
            'country_code',
            'state',
            'city',
            'organization_name',
            'organizational_unit_name',
            'email',
            'common_name',
            'extensions',
            'serial_number',
            'passphrase',
            'created',
            'modified',
        ]
        read_only_fields = ['created', 'modified']
        extra_kwargs = {
            'organization': {'required': True},
            'key_length': {'initial': '2048'},
            'digest': {'initial': 'sha256'},
            'validity_start': {
                'initial': default_validity_start(),
                'default': default_validity_start(),
            },
            'validity_end': {
                'initial': default_ca_validity_end(),
                'default': default_ca_validity_end(),
            },
        }

    def validate_validity_start(self, value):
        if value is None:
            value = default_validity_start()
        return value

    def validate_validity_end(self, value):
        if value is None:
            value = default_ca_validity_end()
        return value


def CaDetail_fields(fields=None):
    """
    Returns the fields for the `CADetailSerializer`.
    """
    fields.remove('extensions')
    fields.remove('passphrase')
    fields.insert(16, 'certificate')
    fields.insert(17, 'private_key')
    return fields


class CaDetailSerializer(BaseSerializer):
    class Meta:
        model = Ca
        fields = CaDetail_fields(CaListSerializer.Meta.fields[:])
        read_only_fields = fields[4:]


def get_import_data(instance):
    data = {
        'name': instance.name,
        'organization': instance.organization,
        'notes': instance.notes,
        'key_length': instance.key_length,
        'digest': instance.digest,
        'validity_start': instance.validity_start,
        'validity_end': instance.validity_end,
        'country_code': instance.country_code,
        'state': instance.state,
        'city': instance.city,
        'organization_name': instance.organization_name,
        'organizational_unit_name': instance.organizational_unit_name,
        'email': instance.email,
        'common_name': instance.common_name,
        'extensions': instance.extensions,
        'serial_number': instance.serial_number,
        'certificate': instance.certificate,
        'private_key': instance.private_key,
        'passphrase': instance.passphrase,
        'created': instance.created,
        'modified': instance.modified,
    }
    return data


class CaImportSerializer(BaseSerializer):
    class Meta:
        model = Ca
        fields = (
            'id',
            'name',
            'organization',
            'certificate',
            'private_key',
            'passphrase',
        )

    def validate(self, data):
        instance = self.instance or self.Meta.model(**data)
        instance.full_clean()
        data = get_import_data(instance)
        return data


def CertList_fields(fields=None):
    """
    Returns the fields for the `CertListSerializer`.
    """
    fields.insert(3, 'ca')
    fields.insert(5, 'revoked')
    return fields


class CertListSerializer(BaseSerializer):

    extensions = serializers.JSONField(
        initial=[],
        help_text=_('additional x509 certificate extensions'),
        write_only=True,
        required=False,
    )
    include_shared = True

    class Meta:
        model = Cert
        fields = CertList_fields(CaListSerializer.Meta.fields[:])
        read_only_fields = ['created', 'modified']
        extra_kwargs = {
            'revoked': {'read_only': True},
            'key_length': {'initial': '2048'},
            'digest': {'initial': 'sha256'},
            'validity_start': {
                'initial': default_validity_start(),
                'default': default_validity_start(),
            },
            'validity_end': {
                'initial': default_cert_validity_end(),
                'default': default_cert_validity_end(),
            },
        }

    def validate_validity_start(self, value):
        if value is None:
            value = default_validity_start()
        return value

    def validate_validity_end(self, value):
        if value is None:
            value = default_cert_validity_end()
        return value


def CertDetail_fields(fields=None):
    """
    Returns the fields for the `CertDetailSerializer`.
    """
    fields.remove('extensions')
    fields.remove('passphrase')
    fields.insert(6, 'revoked_at')
    fields.insert(19, 'certificate')
    fields.insert(20, 'private_key')
    return fields


class CertDetailSerializer(BaseSerializer):
    ca = serializers.StringRelatedField()

    class Meta:
        model = Cert
        fields = CertDetail_fields(CertListSerializer.Meta.fields[:])
        read_only_fields = fields[5:]


class CertImportSerializer(BaseSerializer):
    class Meta:
        model = Cert
        fields = (
            'id',
            'name',
            'organization',
            'ca',
            'certificate',
            'private_key',
            'passphrase',
        )

    def validate(self, data):
        instance = self.instance or self.Meta.model(**data)
        instance.full_clean()
        data = get_import_data(instance)
        data.update({'ca': instance.ca})
        return data
