import uuid
from datetime import datetime, timedelta

import swapper
from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from model_utils.fields import AutoCreatedField, AutoLastModifiedField
from OpenSSL import crypto

from .. import settings as app_settings

KEY_LENGTH_CHOICES = (
    ("256", "256 (ECDSA)"),
    ("384", "384 (ECDSA)"),
    ("521", "521 (ECDSA)"),
    ("1024", "1024 (RSA)"),
    ("2048", "2048 (RSA)"),
    ("4096", "4096 (RSA)"),
)

RSA_KEY_LENGTHS = ("1024", "2048", "4096")
EC_KEY_LENGTHS = ("256", "384", "521")

DIGEST_CHOICES = (
    ("sha1", "SHA1"),
    ("sha224", "SHA224"),
    ("sha256", "SHA256"),
    ("sha384", "SHA384"),
    ("sha512", "SHA512"),
)


def default_validity_start():
    """
    Sets validity_start field to 1 day before the current date
    (avoids "certificate not valid yet" edge case).

    In some cases, because of timezone differences, when certificates
    were just created they were considered valid in a timezone (eg: Europe)
    but not yet valid in another timezone (eg: US).

    This function intentionally returns naive datetime (not timezone aware),
    so that certificates are valid from 00:00 AM in all timezones.
    """
    start = datetime.now() - timedelta(days=1)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def default_ca_validity_end():
    """
    returns the default value for validity_end field
    """
    delta = timedelta(days=app_settings.DEFAULT_CA_VALIDITY)
    return timezone.now() + delta


def default_cert_validity_end():
    """
    returns the default value for validity_end field
    """
    delta = timedelta(days=app_settings.DEFAULT_CERT_VALIDITY)
    return timezone.now() + delta


def default_key_length():
    """
    returns default value for key_length field
    (this avoids to set the exact default value in the database migration)
    """
    return app_settings.DEFAULT_KEY_LENGTH


def default_digest_algorithm():
    """
    returns default value for digest field
    (this avoids to set the exact default value in the database migration)
    """
    return app_settings.DEFAULT_DIGEST_ALGORITHM


class BaseX509(models.Model):
    """
    Abstract Cert class, shared between Ca and Cert
    """

    name = models.CharField(max_length=64)
    notes = models.TextField(blank=True)
    key_length = models.CharField(
        _("key length"),
        help_text=_("bits"),
        choices=KEY_LENGTH_CHOICES,
        default=default_key_length,
        max_length=6,
    )
    digest = models.CharField(
        _("digest algorithm"),
        help_text=_("bits"),
        choices=DIGEST_CHOICES,
        default=default_digest_algorithm,
        max_length=8,
    )
    validity_start = models.DateTimeField(
        blank=True, null=True, default=default_validity_start
    )
    validity_end = models.DateTimeField(
        blank=True, null=True, default=default_cert_validity_end
    )
    country_code = models.CharField(max_length=2, blank=True)
    state = models.CharField(_("state or province"), max_length=64, blank=True)
    city = models.CharField(_("city"), max_length=64, blank=True)
    organization_name = models.CharField(_("organization"), max_length=64, blank=True)
    organizational_unit_name = models.CharField(
        _("organizational unit name"), max_length=64, blank=True
    )
    email = models.EmailField(_("email address"), blank=True)
    common_name = models.CharField(_("common name"), max_length=64, blank=True)
    extensions = models.JSONField(
        _("extensions"),
        default=list,
        blank=True,
        help_text=_("additional x509 certificate extensions"),
    )
    # serial_number is set to CharField as a UUID integer is too big for a
    # PositiveIntegerField and an IntegerField on SQLite
    serial_number = models.CharField(
        _("serial number"),
        help_text=_("leave blank to determine automatically"),
        blank=True,
        null=True,
        max_length=48,
    )
    certificate = models.TextField(
        blank=True, help_text="certificate in X.509 PEM format"
    )
    private_key = models.TextField(
        blank=True, help_text="private key in X.509 PEM format"
    )
    created = AutoCreatedField(_("created"), editable=True)
    modified = AutoLastModifiedField(_("modified"), editable=True)
    passphrase = models.CharField(
        max_length=64,
        blank=True,
        help_text=_("Passphrase for the private key, if present"),
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def clean_fields(self, *args, **kwargs):
        # importing existing certificate
        # must be done here in order to validate imported fields
        # and fill private and public key before validation fails
        if self._state.adding and self.certificate and self.private_key:
            self._validate_pem()
            self._import()
        super().clean_fields(*args, **kwargs)

    def clean(self):
        if self.serial_number:
            self._validate_serial_number()
        self._verify_extension_format()
        # when importing, both public and private must be present
        if (self.certificate and not self.private_key) or (
            self.private_key and not self.certificate
        ):
            raise ValidationError(
                _(
                    "When importing an existing certificate, both "
                    "keys (private and public) must be present"
                )
            )
        all_supported = list(RSA_KEY_LENGTHS) + list(EC_KEY_LENGTHS)
        if self.key_length not in all_supported:
            raise ValidationError(
                {"key_length": _("Unsupported key length: %s") % self.key_length}
            )

    def save(self, *args, **kwargs):
        if self._state.adding and not self.certificate and not self.private_key:
            # auto generate serial number
            if not self.serial_number:
                self.serial_number = self._generate_serial_number()
            self._generate()
        super().save(*args, **kwargs)

    @cached_property
    def x509(self):
        """
        returns an instance of cryptography.x509.Certificate
        """
        if self.certificate:
            return x509.load_pem_x509_certificate(self.certificate.encode("utf-8"))

    @cached_property
    def x509_text(self):
        """
        Uses pyOpenSSL to return a human readable text
        representation of the certificate which is
        equivalent to "openssl x509 -text -noout -in <cert>".
        """
        if self.certificate:
            text = crypto.dump_certificate(
                crypto.FILETYPE_TEXT,
                crypto.load_certificate(crypto.FILETYPE_PEM, self.certificate),
            )
            return text.decode("utf-8")

    @cached_property
    def pkey(self):
        """
        Returns an instance of cryptography private key
        """
        if self.private_key:
            password = self.passphrase.encode("utf-8") if self.passphrase else None
            return serialization.load_pem_private_key(
                self.private_key.encode("utf-8"), password=password
            )
        return None

    def _validate_pem(self):
        """
        (internal use only)
        validates certificate and private key
        """
        errors = {}
        if self.certificate:
            try:
                x509.load_pem_x509_certificate(self.certificate.encode("utf-8"))
            except (ValueError, TypeError, UnsupportedAlgorithm):
                errors["certificate"] = ValidationError(_("Invalid certificate"))
        if self.private_key:
            try:
                password = self.passphrase.encode("utf-8") if self.passphrase else None
                serialization.load_pem_private_key(
                    self.private_key.encode("utf-8"),
                    password=password,
                )
            except (TypeError, ValueError) as e:
                msg = str(e).lower()
                # Distinguish passphrase errors from format errors:
                # - Specific passphrase errors:
                #   "password was not given but private key is encrypted"
                # - Decryption/padding failures indicate wrong passphrase
                # - Generic "password" mentions in parsing errors
                #   should NOT trigger this
                is_passphrase_error = (
                    any(word in msg for word in ["decrypt", "padding"])
                    or "password was not given" in msg
                )
                if is_passphrase_error:
                    errors["passphrase"] = ValidationError(_("Incorrect Passphrase"))
                else:
                    errors["private_key"] = ValidationError(_("Invalid private key"))
            except UnsupportedAlgorithm:
                errors["private_key"] = ValidationError(
                    _("Unsupported private key algorithm")
                )
        if errors:
            raise ValidationError(errors)

    def _validate_serial_number(self):
        """
        (internal use only)
        validates serial number if set manually
        """
        try:
            int(self.serial_number)
        except ValueError:
            raise ValidationError(
                {"serial_number": _("Serial number must be an integer")}
            )

    def _generate(self):
        """
        (internal use only)
        generates a new x509 certificate (CA or end-entity)
        """
        for attr in ["x509", "pkey"]:
            if attr in self.__dict__:
                del self.__dict__[attr]
        is_ec = self.key_length in EC_KEY_LENGTHS
        if is_ec:
            curves = {
                "256": ec.SECP256R1(),
                "384": ec.SECP384R1(),
                "521": ec.SECP521R1(),
            }
            curve = curves.get(self.key_length)
            if not curve:
                raise ValidationError(
                    _("Unsupported EC key length: %s") % self.key_length
                )
            key = ec.generate_private_key(curve)
        else:
            key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=int(self.key_length),
            )
        if hasattr(self, "ca"):
            signing_key = self.ca.pkey
            issuer_name = self.ca.x509.subject
        else:
            signing_key = key
            issuer_name = self._get_subject()
        builder = (
            x509.CertificateBuilder()
            .subject_name(self._get_subject())
            .issuer_name(issuer_name)
            .serial_number(int(self.serial_number))
            .not_valid_before(self.validity_start)
            .not_valid_after(self.validity_end)
            .public_key(key.public_key())
        )
        builder = self._add_extensions(builder, key.public_key())
        HASH_MAP = {
            "sha1": hashes.SHA1,
            "sha224": hashes.SHA224,
            "sha256": hashes.SHA256,
            "sha384": hashes.SHA384,
            "sha512": hashes.SHA512,
        }
        digest_name = (
            self.digest.lower()
            .replace("withrsaencryption", "")
            .replace("ecdsa-with-", "")
            .replace("withsha", "sha")
        )
        digest_alg = HASH_MAP.get(digest_name, hashes.SHA256)()
        cert = builder.sign(signing_key, digest_alg)
        self.certificate = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        encryption = (
            serialization.BestAvailableEncryption(self.passphrase.encode("utf-8"))
            if self.passphrase
            else serialization.NoEncryption()
        )
        self.private_key = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=(
                serialization.PrivateFormat.PKCS8
                if is_ec
                else serialization.PrivateFormat.TraditionalOpenSSL
            ),
            encryption_algorithm=encryption,
        ).decode("utf-8")

    def _get_subject(self):
        """
        (internal use only)
        fills cryptography.x509.Name object
        """
        mapping = {
            "country_code": NameOID.COUNTRY_NAME,
            "state": NameOID.STATE_OR_PROVINCE_NAME,
            "city": NameOID.LOCALITY_NAME,
            "organization_name": NameOID.ORGANIZATION_NAME,
            "organizational_unit_name": NameOID.ORGANIZATIONAL_UNIT_NAME,
            "email": NameOID.EMAIL_ADDRESS,
            "common_name": NameOID.COMMON_NAME,
        }
        attrs = []
        # set x509 subject attributes only if not empty strings
        for model_attr, oid in mapping.items():
            value = getattr(self, model_attr)
            if value:
                # coerce value to string, allow these fields to be redefined
                # as foreign keys by subclasses without losing compatibility
                attrs.append(x509.NameAttribute(oid, str(value)))
        return x509.Name(attrs)

    def _import(self):
        """
        (internal use only)
        imports existing x509 certificates
        """
        cert = self.x509
        public_key = cert.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            actual_length = str(public_key.key_size)
            actual_is_ec = False
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            actual_length = str(public_key.curve.key_size)
            actual_is_ec = True
        else:
            raise ValidationError(
                _(
                    "Unsupported key type in certificate. "
                    "Only RSA and EC keys are supported."
                )
            )
        selected_is_ec = self.key_length in EC_KEY_LENGTHS
        if selected_is_ec != actual_is_ec:
            algorithm_expected = "ECDSA" if selected_is_ec else "RSA"
            algorithm_provided = "ECDSA" if actual_is_ec else "RSA"
            raise ValidationError(
                {
                    "key_length": _(
                        "Algorithm mismatch: You selected a length for %s, "
                        "but the provided certificate contains an %s key."
                    )
                    % (algorithm_expected, algorithm_provided)
                }
            )
        if actual_is_ec and actual_length not in EC_KEY_LENGTHS:
            raise ValidationError(_("Unsupported EC curve size: %s") % actual_length)
        self.key_length = actual_length
        # when importing an end entity certificate
        if hasattr(self, "ca"):
            self._verify_ca()
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )
            emails = ext.value.get_values_for_type(x509.RFC822Name)
            email = emails[0] if emails else ""
        except x509.ExtensionNotFound:
            attrs = cert.subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)
            email = str(attrs[0].value) if attrs else ""

        self.email = email
        self.digest = cert.signature_hash_algorithm.name.lower()
        self.validity_start = cert.not_valid_before_utc
        self.validity_end = cert.not_valid_after_utc

        def get_val(oid):
            attrs = cert.subject.get_attributes_for_oid(oid)
            return str(attrs[0].value) if attrs else ""

        self.country_code = get_val(NameOID.COUNTRY_NAME)
        # allow importing from legacy systems which use invalid country codes
        if len(self.country_code) > 2:
            self.country_code = ""
        self.state = get_val(NameOID.STATE_OR_PROVINCE_NAME)
        self.city = get_val(NameOID.LOCALITY_NAME)
        self.organization_name = get_val(NameOID.ORGANIZATION_NAME)
        self.organizational_unit_name = get_val(NameOID.ORGANIZATIONAL_UNIT_NAME)
        self.common_name = get_val(NameOID.COMMON_NAME)
        self.serial_number = str(cert.serial_number)
        if not self.name:
            self.name = self.common_name or self.serial_number

    def _verify_ca(self):
        """
        (internal use only)
        verifies the current x509 is signed
        by the associated CA
        """
        cert = self.x509
        ca_cert = self.ca.x509
        ca_pubkey = ca_cert.public_key()
        issuer_identity = set(
            (attr.oid, str(attr.value).strip().lower()) for attr in cert.issuer
        )
        ca_identity = set(
            (attr.oid, str(attr.value).strip().lower()) for attr in ca_cert.subject
        )
        if issuer_identity != ca_identity:
            raise ValidationError(
                _("The Certificate Issuer does not match the CA Subject.")
            )
        now = timezone.now()
        if cert.not_valid_before_utc > now or cert.not_valid_after_utc < now:
            raise ValidationError(_("The certificate has expired or is not yet valid."))
        try:
            bc = ca_cert.extensions.get_extension_for_class(x509.BasicConstraints).value
            if not bc.ca:
                raise ValidationError(
                    _(
                        "The selected CA is not authorized to sign certificates"
                        "(BasicConstraints)."
                    )
                )
        except x509.ExtensionNotFound:
            raise ValidationError(
                _("The selected CA is missing BasicConstraints and cannot sign.")
            ) from None
        try:
            if isinstance(ca_pubkey, rsa.RSAPublicKey):
                ca_pubkey.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    padding.PKCS1v15(),
                    cert.signature_hash_algorithm,
                )
            elif isinstance(ca_pubkey, ec.EllipticCurvePublicKey):
                ca_pubkey.verify(
                    cert.signature,
                    cert.tbs_certificate_bytes,
                    ec.ECDSA(cert.signature_hash_algorithm),
                )
            else:
                ca_pubkey.verify(cert.signature, cert.tbs_certificate_bytes)
        except InvalidSignature:
            raise ValidationError(
                _("Cryptographic signature verification failed: CA does not match.")
            )

    def _verify_extension_format(self):
        """
        (internal use only)
        verifies the format of ``self.extension`` is correct
        """
        msg = "Extension format invalid"
        if not isinstance(self.extensions, list):
            raise ValidationError(msg)
        for ext in self.extensions:
            if not isinstance(ext, dict):
                raise ValidationError(msg)
            if not ("name" in ext and "critical" in ext and "value" in ext):
                raise ValidationError(msg)

    def _add_extensions(self, builder, public_key):
        """
        (internal use only)
        Adds x509 extensions to the CertificateBuilder.
        """
        # prepare extensions for CA
        is_ca = not hasattr(self, "ca")
        bc = x509.BasicConstraints(
            ca=is_ca,
            path_length=app_settings.CA_BASIC_CONSTRAINTS_PATHLEN if is_ca else None,
        )
        builder = builder.add_extension(
            bc, critical=app_settings.CA_BASIC_CONSTRAINTS_CRITICAL if is_ca else False
        )
        ku_str = (
            app_settings.CA_KEYUSAGE_VALUE
            if is_ca
            else app_settings.CERT_KEYUSAGE_VALUE
        )
        ku_crit = (
            app_settings.CA_KEYUSAGE_CRITICAL
            if is_ca
            else app_settings.CERT_KEYUSAGE_CRITICAL
        )
        usages = {u.strip().lower() for u in ku_str.split(",")}
        key_usage = x509.KeyUsage(
            digital_signature="digital_signature" in usages
            or "digitalsignature" in usages,
            content_commitment="content_commitment" in usages
            or "nonrepudiation" in usages,
            key_encipherment="key_encipherment" in usages
            or "keyencipherment" in usages,
            data_encipherment="data_encipherment" in usages
            or "dataencipherment" in usages,
            key_agreement="key_agreement" in usages or "keyagreement" in usages,
            key_cert_sign="key_cert_sign" in usages or "keycertsign" in usages,
            crl_sign="crl_sign" in usages or "crlsign" in usages,
            encipher_only="encipher_only" in usages or "encipheronly" in usages,
            decipher_only="decipher_only" in usages or "decipheronly" in usages,
        )
        builder = builder.add_extension(key_usage, critical=ku_crit)
        builder = builder.add_extension(
            x509.SubjectKeyIdentifier.from_public_key(public_key), critical=False
        )
        if hasattr(self, "ca"):
            issuer_cert = self.ca.x509
            try:
                issuer_ski = issuer_cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_KEY_IDENTIFIER
                ).value
                aki = x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                    issuer_ski
                )
            except x509.ExtensionNotFound:
                aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(
                    issuer_cert.public_key()
                )
        else:
            aki = x509.AuthorityKeyIdentifier.from_issuer_public_key(public_key)

        builder = builder.add_extension(aki, critical=False)
        if self.extensions:
            for ext_data in self.extensions:
                name = ext_data.get("name")
                val = ext_data.get("value", "")
                crit = ext_data.get("critical", False)

                if name == "extendedKeyUsage":
                    eku_map = {
                        "clientauth": ExtendedKeyUsageOID.CLIENT_AUTH,
                        "serverauth": ExtendedKeyUsageOID.SERVER_AUTH,
                        "codesigning": ExtendedKeyUsageOID.CODE_SIGNING,
                        "emailprotection": ExtendedKeyUsageOID.EMAIL_PROTECTION,
                    }
                    oids = []
                    for v in val.split(","):
                        v_clean = v.strip().lower()
                        if v_clean not in eku_map:
                            raise ValidationError(
                                _("Unsupported extendedKeyUsage value: %s") % v_clean
                            )
                        oids.append(eku_map[v_clean])
                    if oids:
                        builder = builder.add_extension(
                            x509.ExtendedKeyUsage(oids), critical=crit
                        )

                elif name == "nsComment":
                    if not val:
                        raise ValidationError(
                            _("nsComment extension requires a value.")
                        )
                    if len(val) > 255:
                        raise ValidationError(
                            _("nsComment value exceeds maximum length of 255 bytes")
                        )
                    raw_val = b"\x16" + bytes([len(val)]) + val.encode("utf-8")
                    builder = builder.add_extension(
                        x509.UnrecognizedExtension(
                            x509.ObjectIdentifier("2.16.840.1.113730.1.13"), raw_val
                        ),
                        critical=crit,
                    )

                elif name == "nsCertType":
                    ns_cert_type_map = {
                        "client": 0x80,
                        "server": 0x40,
                        "email": 0x20,
                        "objsign": 0x10,
                        "sslca": 0x04,
                        "emailca": 0x02,
                        "objca": 0x01,
                    }
                    bits = 0
                    for v in val.split(","):
                        v_clean = v.strip().lower()
                        if v_clean not in ns_cert_type_map:
                            raise ValidationError(
                                _("Unsupported nsCertType value: %s") % v_clean
                            )
                        bits |= ns_cert_type_map[v_clean]
                    if not bits:
                        raise ValidationError(
                            _("nsCertType extension requires at least one valid type.")
                        )
                    raw_val = bytes([0x03, 0x02, 0x07, bits])
                    builder = builder.add_extension(
                        x509.UnrecognizedExtension(
                            x509.ObjectIdentifier("2.16.840.1.113730.1.1"),
                            raw_val,
                        ),
                        critical=crit,
                    )
                else:
                    raise ValidationError(_("Unsupported extension: %s") % name)
        return builder

    def renew(self):
        self.serial_number = self._generate_serial_number()
        if hasattr(self, "ca"):
            self.validity_end = default_cert_validity_end()
        else:
            self.validity_end = default_ca_validity_end()
        self._generate()
        self.save()

    def _generate_serial_number(self):
        return uuid.uuid4().int


class AbstractCa(BaseX509):
    """
    Abstract Ca model
    """

    class Meta:
        abstract = True
        verbose_name = _("CA")
        verbose_name_plural = _("CAs")

    def get_revoked_certs(self):
        """
        Returns revoked certificates of this CA
        (does not include expired certificates)
        """
        now = timezone.now()
        return self.cert_set.filter(
            revoked=True, validity_start__lte=now, validity_end__gte=now
        )

    def renew(self):
        """
        Renew the certificate, private key and
        validity end date of a CA
        """
        super().renew()
        children = getattr(self, "issued_certificates", getattr(self, "cert_set", None))
        if children:
            for cert in children.all():
                cert.ca = self
                cert.renew()

    @property
    def crl(self):
        """
        Returns up to date CRL of this CA
        """
        ca_cert = x509.load_pem_x509_certificate(self.certificate.encode())
        pkey_kwargs = {"password": None}
        if self.passphrase:
            pkey_kwargs["password"] = self.passphrase.encode()
        private_key = serialization.load_pem_private_key(
            self.private_key.encode(), **pkey_kwargs
        )
        now = timezone.now()
        builder = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(ca_cert.subject)
            .last_update(now)
            .next_update(now + timedelta(days=1))
        )
        for cert in self.get_revoked_certs():
            revoked = (
                x509.RevokedCertificateBuilder()
                .serial_number(int(cert.serial_number))
                .revocation_date(now)
                .add_extension(
                    x509.CRLReason(x509.ReasonFlags.unspecified),
                    critical=False,
                )
                .build()
            )
            builder = builder.add_revoked_certificate(revoked)
        crl = builder.sign(
            private_key=private_key,
            algorithm=hashes.SHA256(),
        )
        return crl.public_bytes(encoding=serialization.Encoding.PEM)


AbstractCa._meta.get_field("validity_end").default = default_ca_validity_end


class AbstractCert(BaseX509):
    """
    Abstract Cert model
    """

    ca = models.ForeignKey(
        swapper.get_model_name("django_x509", "Ca"),
        on_delete=models.CASCADE,
        verbose_name=_("CA"),
    )
    revoked = models.BooleanField(_("revoked"), default=False)
    revoked_at = models.DateTimeField(
        _("revoked at"), blank=True, null=True, default=None
    )

    def __str__(self):
        return self.name

    class Meta:
        abstract = True
        verbose_name = _("certificate")
        verbose_name_plural = _("certificates")
        unique_together = ("ca", "serial_number")

    def revoke(self):
        """
        * flag certificate as revoked
        * fill in revoked_at DateTimeField
        """
        now = timezone.now()
        self.revoked = True
        self.revoked_at = now
        self.save()
