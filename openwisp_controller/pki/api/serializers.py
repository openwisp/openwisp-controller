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
    key_length = serializers.ChoiceField(
        allow_blank=False,
        choices=(('512', '512'), ('1024', '1024'), ('2048', '2048'), ('4096', '4096')),
        help_text=_('bits'),
        initial='2048',
        required=True,
    )
    digest = serializers.ChoiceField(
        allow_blank=False,
        choices=(
            ('sha1', 'SHA1'),
            ('sha224', 'SHA224'),
            ('sha256', 'SHA256'),
            ('sha384', 'SHA384'),
            ('sha512', 'SHA512'),
        ),
        help_text=_('bits'),
        initial='sha256',
        label='Digest algorithm',
        required=True,
    )
    validity_start = serializers.DateTimeField(
        allow_null=False,
        initial=default_validity_start(),
        default=default_validity_start(),
    )
    validity_end = serializers.DateTimeField(
        allow_null=False,
        initial=default_ca_validity_end(),
        default=default_ca_validity_end(),
    )
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
        }


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


def CertList_fields(fields=None):
    """
    Returns the fields for the `CertListSerializer`.
    """
    fields.insert(3, 'ca')
    fields.insert(5, 'revoked')
    return fields


class CertListSerializer(BaseSerializer):
    key_length = serializers.ChoiceField(
        allow_blank=False,
        choices=(('512', '512'), ('1024', '1024'), ('2048', '2048'), ('4096', '4096')),
        help_text=_('bits'),
        initial='2048',
        required=True,
    )
    digest = serializers.ChoiceField(
        allow_blank=False,
        choices=(
            ('sha1', 'SHA1'),
            ('sha224', 'SHA224'),
            ('sha256', 'SHA256'),
            ('sha384', 'SHA384'),
            ('sha512', 'SHA512'),
        ),
        help_text=_('bits'),
        initial='sha256',
        label='Digest algorithm',
        required=True,
    )
    validity_start = serializers.DateTimeField(
        allow_null=False,
        initial=default_validity_start(),
        default=default_validity_start(),
    )
    validity_end = serializers.DateTimeField(
        allow_null=False,
        initial=default_cert_validity_end(),
        default=default_cert_validity_end(),
    )
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
        }


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
