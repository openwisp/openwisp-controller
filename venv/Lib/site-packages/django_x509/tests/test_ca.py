from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .. import settings as app_settings
from . import UTC_TIME, Ca, TestX509Mixin, datetime_to_string


def get_crl_revoked_certs(crl):
    crl = x509.load_pem_x509_crl(crl)
    return [cert for cert in crl]


class TestCa(TestX509Mixin, TestCase):
    """
    tests for Ca model
    """

    app_label = Ca._meta.app_label

    def _prepare_revoked(self):
        ca = self._create_ca()
        revoked_certs = get_crl_revoked_certs(ca.crl)
        self.assertEqual(revoked_certs, [])
        cert = self._create_cert(ca=ca)
        cert.revoke()
        return (ca, cert)

    import_certificate = """-----BEGIN CERTIFICATE-----
MIIDzzCCAregAwIBAgIUQSTDetixAO35vLfJ7jlCH7/UpUcwDQYJKoZIhvcNAQEL
BQAwdzETMBEGA1UEAwwKaW1wb3J0dGVzdDELMAkGA1UEBhMCVVMxCzAJBgNVBAgM
AkNBMRYwFAYDVQQHDA1TYW4gRnJhbmNpc2NvMQ0wCwYDVQQKDARBQ01FMR8wHQYJ
KoZIhvcNAQkBFhBjb250YWN0QGFjbWUuY29tMB4XDTI2MDExNzA3NDEwNVoXDTM2
MDExNTA3NDEwNVowdzETMBEGA1UEAwwKaW1wb3J0dGVzdDELMAkGA1UEBhMCVVMx
CzAJBgNVBAgMAkNBMRYwFAYDVQQHDA1TYW4gRnJhbmNpc2NvMQ0wCwYDVQQKDARB
Q01FMR8wHQYJKoZIhvcNAQkBFhBjb250YWN0QGFjbWUuY29tMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkyNsaGZatFTvlPQ2Soj4g5kzalPmrLkKEXxY
kNvICJ430Pob1J0N+R5VdhNuwuSaCc4bj5lzyHCvScSZBaTyThXX6deRUW1uk8Ss
8fG+E8JCrAHzKWQVUe7uZJTgKtI6hNBfNzmVHVXvWiFBQRMO4OXOW92hKKPhOIcc
T99QcelNrO1TKT937cngKaSb+0ZcoAspKWfFb0y62XxxArHC/f5nN2p1I8+6h9gQ
26+MRXmxwlvT9qX2TMRBCj36D0jgsCgJ10C7iQjZu3d5FtmbU7dS4DvlCj8pNXcn
S4RxXHrmZKeY3UVk9TNRYyMOd2cHm7FQdrGYWO4xT+5LtPkLcQIDAQABo1MwUTAd
BgNVHQ4EFgQUrnxElH6h9VmQZYHG+aGHSuhDayMwHwYDVR0jBBgwFoAUrnxElH6h
9VmQZYHG+aGHSuhDayMwDwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOC
AQEACshO+uDpXE779/5zrm6w83IKJHqYnX2pdFMJM1WuJBXlo0r+WMrwDTarQc+I
NhuL60bnoYrmrja8o5cOuBBMqpIn2ct1H7xE4C0t6BY4+khmEBLM700oxKWhOThG
IKAcdLrbqGECQdbttMS5kiMhlH5mQANtnPQFHZgua/kPrBjIeeOzK0Wt+2Lnd3/o
q24y18BVEbJAZxTsEberrvrSAxrdSNk9A4nMrz5UpjOxJ4QWKJctGjUjZrCtpLqP
/fPO6RV+C1jIBYvP2NduuCiQgCqfRArPqhqqWbQodUCwBL8mTu/piL5e1dIotYwH
EQZrw8bbikXRSH3D31NVroN7fw==
-----END CERTIFICATE-----"""

    import_private_key = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCTI2xoZlq0VO+U
9DZKiPiDmTNqU+asuQoRfFiQ28gInjfQ+hvUnQ35HlV2E27C5JoJzhuPmXPIcK9J
xJkFpPJOFdfp15FRbW6TxKzx8b4TwkKsAfMpZBVR7u5klOAq0jqE0F83OZUdVe9a
IUFBEw7g5c5b3aEoo+E4hxxP31Bx6U2s7VMpP3ftyeAppJv7RlygCykpZ8VvTLrZ
fHECscL9/mc3anUjz7qH2BDbr4xFebHCW9P2pfZMxEEKPfoPSOCwKAnXQLuJCNm7
d3kW2ZtTt1LgO+UKPyk1dydLhHFceuZkp5jdRWT1M1FjIw53ZwebsVB2sZhY7jFP
7ku0+QtxAgMBAAECggEANH9kE4/JdyQC41uK72cVfCayMJLE8AWJcRmzo+O26FRD
R/2k5mQu8x5+kYV3dHQJ/cubC85NgEusTx6lFl120qN6iQWP5MStum1m42BEWFps
XWDIuJDsBnLAfgScQssFdBPAlTynVnMt1jOdS7GYEmgMC7z03kIyfm++i0T7N9ji
fyN2CFOXgevgHK5EtTSrBTzg8JkFnhNZKjHPU9IkRyaN8KtOwKrEgxh0glvNM6yp
cmU8PE+DPK4TSQGsIO4X4Z19wKv7O8x6CYLos8w2Yh9jwMHaGeDnv68RVFoY1vgH
q/PJcWylRanDeyoShIm3v2qBCQcBtUqDUqdTotww7QKBgQDH2LeZ4rn7SUuRkt7l
YeM4YtlbWSlycTh1KphqkM3UW0MQA/HcJKgFacbxdEj9hV0Ol/l76qQv39V1Ts3X
Zsf1eSGLdrvi2JYrlh0WYhFco/g7Cqt43dNfqSAnNKb8ihRq3X8zsQ7nTDU3wWoK
fYjeHyYRFYPi7jQF3sYcmrM5OwKBgQC8e1KPKQ2eIJNC5rYbolxRgrSOMxr+AxgD
iiNdhPT0lpeYEPW65z/pbdiiehXt8zrrJhtfDDe7f0dHaYkbSJWq5dzjAqnfwNGO
+gr5+skTL5nkimjbinGHN8+2134eMxh4WmsyQvkY23wk8SJlC9/57/TQvjRNZUAw
nmBmQdojQwKBgQCWFXl9RjqqLxdjkkt3NRZxyDq4UbPA0Kq3w2+HyIvryUYKBwxi
ad0Ng6z2tIAEdV23kga5OzRnB9DFMpOACx5sibXZiSf9au8MeMYLg0bKrhHENXUl
ZmJR2y/cgbxOuFwxDXt0FKq+pgrpfoXmrvRU7EuoVOIhUQccyXs7DCtA9QKBgEoS
vVN98tgePUGhohgiKt3t3D+2XflOBfX+J//s7MfjFxiwMaKOl1OJ1AWmrU+is5kO
lNs51f1d/AlYtIWAdTGAvNqKhXBmOvVR11Z+9N8Rag2jR6pgMlXN3VgiQHJl6kwC
XPaX04WtXJC4I6hKjm+PmksfNTblf+CbnY8SekQ5AoGBALvK6n2UGG+0fKtUFM+M
0enYrqW065OsDOIXo7roOVZjBhul+vilk7xJ85fhtDD0zll/4OoJ1BG9IN0rUUJh
eMIi3AQRO060kYejKGC2ls5hMxjdhxB/bUGrwXkMxZQPfjBkcP3JqaZkwcFBKq5N
tsND+97h9r73S+UTOhepQTDB
-----END PRIVATE KEY-----"""

    def test_new(self):
        ca = self._create_ca()
        self.assertNotEqual(ca.certificate, "")
        self.assertNotEqual(ca.private_key, "")
        cert = ca.x509
        self.assertEqual(cert.serial_number, int(ca.serial_number))

        def get_attr(name_obj, oid):
            attrs = name_obj.get_attributes_for_oid(oid)
            return attrs[0].value if attrs else ""

        ext = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertEqual(
            ext.value.path_length, app_settings.CA_BASIC_CONSTRAINTS_PATHLEN
        )

        self.assertEqual(get_attr(cert.subject, NameOID.COUNTRY_NAME), ca.country_code)
        self.assertEqual(
            get_attr(cert.subject, NameOID.STATE_OR_PROVINCE_NAME), ca.state
        )
        self.assertEqual(get_attr(cert.subject, NameOID.LOCALITY_NAME), ca.city)
        self.assertEqual(
            get_attr(cert.subject, NameOID.ORGANIZATION_NAME), ca.organization_name
        )
        self.assertEqual(get_attr(cert.subject, NameOID.EMAIL_ADDRESS), ca.email)
        self.assertEqual(get_attr(cert.subject, NameOID.COMMON_NAME), ca.common_name)
        self.assertEqual(cert.issuer, cert.subject)
        # ensure version is 3
        self.assertEqual(cert.version, x509.Version.v3)
        # basic constraints
        ext = cert.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertTrue(ext.critical)
        self.assertTrue(ext.value.ca)

    def test_x509_property(self):
        ca = self._create_ca()
        cert_from_pem = x509.load_pem_x509_certificate(ca.certificate.encode())
        self.assertEqual(ca.x509.subject, cert_from_pem.subject)
        self.assertEqual(ca.x509.issuer, cert_from_pem.issuer)
        self.assertEqual(ca.x509.serial_number, cert_from_pem.serial_number)

    def test_x509_property_none(self):
        self.assertIsNone(Ca().x509)

    def test_pkey_property(self):
        ca = self._create_ca()
        self.assertIsInstance(ca.pkey, rsa.RSAPrivateKey)

    def test_pkey_property_none(self):
        self.assertIsNone(Ca().pkey)

    def test_default_validity_end(self):
        ca = Ca()
        self.assertEqual(ca.validity_end.year, datetime.now().year + 10)

    def test_default_validity_start(self):
        ca = Ca()
        expected = datetime.now() - timedelta(days=1)
        self.assertEqual(ca.validity_start.year, expected.year)
        self.assertEqual(ca.validity_start.month, expected.month)
        self.assertEqual(ca.validity_start.day, expected.day)
        self.assertEqual(ca.validity_start.hour, 0)
        self.assertEqual(ca.validity_start.minute, 0)
        self.assertEqual(ca.validity_start.second, 0)

    def test_import_ca(self):
        ca = Ca(name="ImportTest")
        ca.certificate = self.import_certificate
        ca.private_key = self.import_private_key
        ca.full_clean()
        ca.save()
        cert = ca.x509
        # verify attributes
        serial = 371904255628934431598705194442539630076148098375
        self.assertEqual(cert.serial_number, serial)
        subject = cert.subject
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value, "US"
        )
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.STATE_OR_PROVINCE_NAME)[0].value,
            "CA",
        )
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.LOCALITY_NAME)[0].value,
            "San Francisco",
        )
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value, "ACME"
        )
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.EMAIL_ADDRESS)[0].value,
            "contact@acme.com",
        )
        self.assertEqual(
            subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value, "importtest"
        )
        self.assertEqual(cert.issuer, cert.subject)
        # verify field attribtues
        self.assertEqual(ca.key_length, "2048")
        self.assertEqual(ca.digest, "sha256")
        self.assertEqual(ca.country_code, "US")
        self.assertEqual(ca.state, "CA")
        self.assertEqual(ca.city, "San Francisco")
        self.assertEqual(ca.organization_name, "ACME")
        self.assertEqual(ca.email, "contact@acme.com")
        self.assertEqual(ca.common_name, "importtest")
        self.assertEqual(int(ca.serial_number), serial)
        self.assertEqual(ca.name, "ImportTest")
        start = datetime(2026, 1, 17, 7, 41, 5, tzinfo=dt_timezone.utc)
        end = datetime(2036, 1, 15, 7, 41, 5, tzinfo=dt_timezone.utc)
        self.assertEqual(ca.validity_start, start)
        self.assertEqual(ca.validity_end, end)
        #  ensure version is 3
        self.assertEqual(cert.version, x509.Version.v3)
        ca.delete()
        # test auto name
        ca = Ca(
            certificate=self.import_certificate, private_key=self.import_private_key
        )
        ca.full_clean()
        ca.save()
        self.assertEqual(ca.name, "importtest")

    def test_import_private_key_empty(self):
        ca = Ca(name="ImportTest")
        ca.certificate = self.import_certificate
        try:
            ca.full_clean()
        except ValidationError as e:
            # verify error message
            self.assertIn("importing an existing certificate", str(e))
        else:
            self.fail("ValidationError not raised")

    def test_basic_constraints_not_critical(self):
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_CRITICAL", False)
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertFalse(ext.critical)
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_CRITICAL", True)

    def test_basic_constraints_pathlen(self):
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_PATHLEN", 2)
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertEqual(ext.value.path_length, 2)
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_PATHLEN", 0)

    def test_basic_constraints_pathlen_none(self):
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_PATHLEN", None)
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertIsNone(ext.value.path_length)
        setattr(app_settings, "CA_BASIC_CONSTRAINTS_PATHLEN", 0)

    def test_keyusage(self):
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertTrue(ext.critical)
        self.assertTrue(ext.value.key_cert_sign)
        self.assertTrue(ext.value.crl_sign)

    def test_keyusage_not_critical(self):
        setattr(app_settings, "CA_KEYUSAGE_CRITICAL", False)
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertFalse(ext.critical)
        setattr(app_settings, "CA_KEYUSAGE_CRITICAL", True)

    def test_keyusage_value(self):
        setattr(app_settings, "CA_KEYUSAGE_VALUE", "cRLSign, keyCertSign, keyAgreement")
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertTrue(ext.value.crl_sign)
        self.assertTrue(ext.value.key_cert_sign)
        self.assertTrue(ext.value.key_agreement)
        self.assertFalse(ext.value.digital_signature)
        setattr(app_settings, "CA_KEYUSAGE_VALUE", "cRLSign, keyCertSign")

    def test_subject_key_identifier(self):
        ca = self._create_ca()
        ext = ca.x509.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        self.assertFalse(ext.critical)
        ski = x509.SubjectKeyIdentifier.from_public_key(ca.pkey.public_key())
        self.assertEqual(ext.value, ski)

    def test_authority_key_identifier(self):
        ca = self._create_ca()
        aki = ca.x509.extensions.get_extension_for_class(
            x509.AuthorityKeyIdentifier
        ).value
        ski = ca.x509.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        ).value
        self.assertEqual(aki.key_identifier, ski.digest)

    def test_extensions(self):
        extensions = [
            {
                "name": "nsComment",
                "critical": False,
                "value": "CA - autogenerated Certificate",
            }
        ]
        ca = self._create_ca(extensions=extensions)
        oid = x509.ObjectIdentifier("2.16.840.1.113730.1.13")
        ext = ca.x509.extensions.get_extension_for_oid(oid)
        self.assertFalse(ext.critical)
        self.assertEqual(ext.value.value, b"\x16\x1eCA - autogenerated Certificate")

    def test_extensions_error1(self):
        extensions = {}
        try:
            self._create_ca(extensions=extensions)
        except ValidationError as e:
            msg = e.message_dict.get("__all__", [str(e)])[0]
            self.assertIn("Extension format invalid", str(msg))
        else:
            self.fail("ValidationError not raised")

    def test_extensions_error2(self):
        extensions = [{"wrong": "wrong"}]
        try:
            self._create_ca(extensions=extensions)
        except ValidationError as e:
            # verify error message
            msg = e.message_dict.get("__all__", [str(e)])[0]
            self.assertIn("Extension format invalid", str(msg))
        else:
            self.fail("ValidationError not raised")

    def test_get_revoked_certs(self):
        ca = self._create_ca()
        c1 = self._create_cert(ca=ca)
        c2 = self._create_cert(ca=ca)
        self._create_cert(ca=ca)
        self.assertEqual(ca.get_revoked_certs().count(), 0)
        c1.revoke()
        self.assertEqual(ca.get_revoked_certs().count(), 1)
        c2.revoke()
        self.assertEqual(ca.get_revoked_certs().count(), 2)
        now = timezone.now()
        # expired certificates are not counted
        start = now - timedelta(days=6650)
        end = now - timedelta(days=6600)
        c4 = self._create_cert(ca=ca, validity_start=start, validity_end=end)
        c4.revoke()
        self.assertEqual(ca.get_revoked_certs().count(), 2)
        # inactive not counted yet
        start = now + timedelta(days=2)
        end = now + timedelta(days=365)
        c5 = self._create_cert(ca=ca, validity_start=start, validity_end=end)
        c5.revoke()
        self.assertEqual(ca.get_revoked_certs().count(), 2)

    def test_crl(self):
        ca, cert = self._prepare_revoked()
        revoked_list = get_crl_revoked_certs(ca.crl)
        self.assertEqual(len(revoked_list), 1)
        self.assertEqual(revoked_list[0].serial_number, int(cert.serial_number))

    def test_crl_view(self):
        ca, cert = self._prepare_revoked()
        path = reverse("admin:crl", args=[ca.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        revoked_list = get_crl_revoked_certs(response.content)
        self.assertEqual(len(revoked_list), 1)
        self.assertEqual(revoked_list[0].serial_number, int(cert.serial_number))

    def test_crl_view_403(self):
        setattr(app_settings, "CRL_PROTECTED", True)
        ca, _ = self._prepare_revoked()
        response = self.client.get(reverse("admin:crl", args=[ca.pk]))
        self.assertEqual(response.status_code, 403)
        setattr(app_settings, "CRL_PROTECTED", False)

    def test_crl_view_404(self):
        self._prepare_revoked()
        response = self.client.get(reverse("admin:crl", args=[10]))
        self.assertEqual(response.status_code, 404)

    def test_x509_text(self):
        ca = self._create_ca()
        text = ca.x509_text
        # Verify OpenSSL-style text output format
        # OpenSSL displays serial numbers in hex format separated by colons
        self.assertIn("Certificate:", text)
        self.assertIn("Data:", text)
        self.assertIn("Version:", text)
        self.assertIn("Serial Number:", text)
        # Serial number in OpenSSL format (hex with colons)
        self.assertRegex(text, r"Serial Number:\s*\n\s+[0-9a-f]{2}(?::[0-9a-f]{2})+")
        self.assertIn("Signature Algorithm:", text)
        self.assertIn("Issuer:", text)
        self.assertIn("Validity", text)
        self.assertIn("Not Before:", text)
        self.assertIn("Not After :", text)
        self.assertIn("Subject:", text)
        self.assertIn(ca.common_name, text)
        self.assertIn("Subject Public Key Info:", text)
        self.assertIn("X509v3 extensions:", text)
        self.assertIn("X509v3 Basic Constraints:", text)
        self.assertIn("CA:TRUE", text)
        # ensure it's not PEM
        self.assertNotIn("-----BEGIN CERTIFICATE-----", text)

    def test_x509_import_exception_fixed(self):
        certificate = """-----BEGIN CERTIFICATE-----
MIIEBTCCAu2gAwIBAgIBATANBgkqhkiG9w0BAQUFADBRMQswCQYDVQQGEwJJVDEL
MAkGA1UECAwCUk0xDTALBgNVBAcMBFJvbWExDzANBgNVBAoMBkNpbmVjYTEVMBMG
A1UEAwwMUHJvdmEgQ2luZWNhMB4XDTE2MDkyMTA5MDQyOFoXDTM2MDkyMTA5MDQy
OFowUTELMAkGA1UEBhMCSVQxCzAJBgNVBAgMAlJNMQ0wCwYDVQQHDARSb21hMQ8w
DQYDVQQKDAZDaW5lY2ExFTATBgNVBAMMDFByb3ZhIENpbmVjYTCCASIwDQYJKoZI
hvcNAQEBBQADggEPADCCAQoCggEBAMV26pysBdm3OqhyyZjbWZ3ThmH6QTIDScTj
+1y3nGgnIwgpHWJmZiO/XrwYburLttE+NP7qwgtRcVoxTJFnhuunSei8vE9lyooD
l1wRUU0qMZSWB/Q3OF+S+FhRMtymx+H6a46yC5Wqxk0apNlvAJ1avuBtZjvipQHS
Z3ub5iHpHr0LZKYbqq2yXna6SbGUjnGjVieIXTilbi/9yjukhNvoHC1fSXciV8hO
8GFuR5bUF/6kQFFMZsk3vXNTsKVx5ef7+zpN6n8lGmNAC8D28EqBxar4YAhuu8Jw
+gvguEOji5BsF8pTu4NVBXia0xWjD1DKLmueVLu9rd4l2HGxsA0CAwEAAaOB5zCB
5DAMBgNVHRMEBTADAQH/MC0GCWCGSAGG+EIBDQQgFh5DQSAtIGF1dG9nZW5lcmF0
ZWQgQ2VydGlmaWNhdGUwCwYDVR0PBAQDAgEGMB0GA1UdDgQWBBQjUcBhP7i26o7R
iaVbmRStMVsggTB5BgNVHSMEcjBwgBQjUcBhP7i26o7RiaVbmRStMVsggaFVpFMw
UTELMAkGA1UEBhMCSVQxCzAJBgNVBAgMAlJNMQ0wCwYDVQQHDARSb21hMQ8wDQYD
VQQKDAZDaW5lY2ExFTATBgNVBAMMDFByb3ZhIENpbmVjYYIBATANBgkqhkiG9w0B
AQUFAAOCAQEAg0yQ8CGHGl4p2peALn63HxkAxKzxc8bD/bCItXHq3QFJAYRe5nuu
eGBMdlVvlzh+N/xW1Jcl3+dg9UOlB5/eFr0BWXyk/0vtnJoMKjc4eVAcOlcbgk9s
c0J4ZACrfjbBH9bU7OgYy4NwVXWQFbQqDZ4/beDnuA8JZcGV5+gK3H85pqGBndev
4DUTCrYk+kRLMyWLfurH7dSyw/9DXAmOVPB6SMkTK6sqkhwUmT6hEdADFUBTujes
AjGrlOCMA8XDvvxVEl5nA6JjoPAQ8EIjYvxMykZE+nk0ZO4mqMG5DWCp/2ggodAD
tnpHdm8yeMsoFPm+yZVDHDXjAirS6MX28w==
-----END CERTIFICATE-----"""
        private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAxXbqnKwF2bc6qHLJmNtZndOGYfpBMgNJxOP7XLecaCcjCCkd
YmZmI79evBhu6su20T40/urCC1FxWjFMkWeG66dJ6Ly8T2XKigOXXBFRTSoxlJYH
9Dc4X5L4WFEy3KbH4fprjrILlarGTRqk2W8AnVq+4G1mO+KlAdJne5vmIekevQtk
phuqrbJedrpJsZSOcaNWJ4hdOKVuL/3KO6SE2+gcLV9JdyJXyE7wYW5HltQX/qRA
UUxmyTe9c1OwpXHl5/v7Ok3qfyUaY0ALwPbwSoHFqvhgCG67wnD6C+C4Q6OLkGwX
ylO7g1UFeJrTFaMPUMoua55Uu72t3iXYcbGwDQIDAQABAoIBAD2pWa/c4+LNncqW
Na++52gqcm9MB2nHrxSFoKueRoAboIve0uc0VLba/ok8E/7L6GXEyCXGRxvjrcLd
XCyXqIET9zdvIFqmza11W6GLYtj20Q62Hvu69qaZrWVezcQrbIV7fnTL0mRFNLFF
Ha8sQ4Pfn3VTlDYlGyPLgTcPQrjZlwD5OlzRNEbko/LkdNXZ3pvf4q17pjsxP3E7
XqD+d+dny+pBZL748Hp1RmNo/XfhF2Y4iIV4+3/CyBiTlnn8sURqQCeuoA42iCIH
y28SBz0WS2FD/yVNbH0c4ZU+/R3Fwz5l7sHfaBieJeTFeqr5kuRU7Rro0EfFpa41
rT3fTz0CgYEA9/XpNsMtRLoMLqb01zvylgLO1cKNkAmoVFhAnh9nH1n3v55Vt48h
K9NkHUPbVwSIVdQxDzQy+YXw9IEjieVCBOPHTxRHfX90Azup5dFVXznw6qs1GiW2
mXK+fLToVoTSCi9sHIbIkCAnKS7B5hzKxu+OicKKvouo7UM/NWiSGpsCgYEAy93i
gN8leZPRSGXgS5COXOJ7zf8mqYWbzytnD5wh3XjWA2SNap93xyclCB7rlMfnOAXy
9rIgjrDEBBW7BwUyrYcB8M/qLvFfuf3rXgdhVzvA2OctdUdyzGERXObhiRopa2kq
jFj4QyRa5kv7VTe85t9Ap2bqpE2nVD1wxRdaFncCgYBN0M+ijvfq5JQkI+MclMSZ
jUIJ1WeFt3IrHhMRTHuZXCui5/awh2t6jHmTsZLpKRP8E35d7hy9L+qhYNGdWeQx
Eqaey5dv7AqlZRj5dYtcOhvAGYCttv4qA9eB3Wg4lrAv4BgGj8nraRvBEdpp88kz
S0SpOPM/vyaBZyQ0B6AqVwKBgQCvDvV03Cj94SSRGooj2RmmQQU2uqakYwqMNyTk
jpm16BE+EJYuvIjKBp8R/hslQxMVVGZx2DuEy91F9LMJMDl4MLpF4wOhE7uzpor5
zzSTB8htePXcA2Jche227Ls2U7TFeyUCJ1Pns8wqfYxwfNBFH+gQ15sdQ2EwQSIY
3BiLuQKBgGG+yqKnBceb9zybnshSAVdGt933XjEwRUbaoXGnHjnCxsTtSGa0JkCT
2yrYrwM4KOr7LrKtvz703ApicJf+oRO+vW27+N5t0pyLCjsYJyL55RpM0KWJhKhT
KQV8C/ciDV+lIw2yBmlCNvUmy7GAsHSZM+C8y29+GFR7an6WV+xa
-----END RSA PRIVATE KEY-----"""
        ca = Ca(
            name="ImportTest error", certificate=certificate, private_key=private_key
        )
        ca.full_clean()
        ca.save()
        self.assertEqual(ca.email, "")

    def test_fill_subject_non_strings(self):
        ca1 = self._create_ca()
        ca2 = Ca(name="ca", organization_name=ca1)
        subject = ca2._get_subject()
        org_name = subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
        self.assertEqual(org_name, "Test CA")

    # this certificate has an invalid country code
    problematic_certificate = """-----BEGIN CERTIFICATE-----
MIIEjzCCA3egAwIBAgIBATANBgkqhkiG9w0BAQUFADB9MQ8wDQYDVQQGEwZJdGFs
aWExFjAUBgNVBAgMDUxhbWV6aWEgVGVybWUxFjAUBgNVBAcMDUxhbWV6aWEgVGVy
bWUxIDAeBgNVBAoMF0NvbXVuZSBkaSBMYW1lemlhIFRlcm1lMRgwFgYDVQQDDA9M
YW1lemlhZnJlZXdpZmkwHhcNMTIwMjE3MTQzMzAyWhcNMjIwMjE3MTQzMzAyWjB9
MQ8wDQYDVQQGEwZJdGFsaWExFjAUBgNVBAgMDUxhbWV6aWEgVGVybWUxFjAUBgNV
BAcMDUxhbWV6aWEgVGVybWUxIDAeBgNVBAoMF0NvbXVuZSBkaSBMYW1lemlhIFRl
cm1lMRgwFgYDVQQDDA9MYW1lemlhZnJlZXdpZmkwggEiMA0GCSqGSIb3DQEBAQUA
A4IBDwAwggEKAoIBAQDBsEbRkpsgl9PZO+eb6M+2XDuENaDKIWxzEqhlQWqfivM5
SJNpIBij9n8vIgRu2ie7DmomBkU93tQWwL5EcZcSuqAnBgzkNmko5bsk9w7v6Apq
V4UckIhtie7KRDCrG1XJaZ/0V4uYcW7+d1fYTCfMcgchpzMQsHAdjikyzRXc5TJn
noV6eZf76zQGSaZllwl90VwQvEVe3VCKSja+zpYxsOjQgnKgrDx1O0l/RGxtCWGG
fY9bizlD01nH4WuMT9ObO9F1YqnBc7pWtmRm4DfArr3yW5LKxkRrilwV1UCgQ80z
yMYSeEIufChexzo1JBzrL7aEKnSm5fDvt3iJV3OlAgMBAAGjggEYMIIBFDAMBgNV
HRMEBTADAQH/MC0GCWCGSAGG+EIBDQQgFh5DQSAtIGF1dG9nZW5lcmF0ZWQgQ2Vy
dGlmaWNhdGUwCwYDVR0PBAQDAgEGMB0GA1UdDgQWBBSsrs2asN5B2nSL36P72EBR
MOLgijCBqAYDVR0jBIGgMIGdgBSsrs2asN5B2nSL36P72EBRMOLgiqGBgaR/MH0x
DzANBgNVBAYTBkl0YWxpYTEWMBQGA1UECAwNTGFtZXppYSBUZXJtZTEWMBQGA1UE
BwwNTGFtZXppYSBUZXJtZTEgMB4GA1UECgwXQ29tdW5lIGRpIExhbWV6aWEgVGVy
bWUxGDAWBgNVBAMMD0xhbWV6aWFmcmVld2lmaYIBATANBgkqhkiG9w0BAQUFAAOC
AQEAf6qG2iFfTv31bOWeE2GBO5VyT1l2MjB/waAXT4vPE2P3RVMoZguBZLc3hmbx
nF6L5JlG7VbRqEE8wJMS5WeURuJe94CVftXJhzcd8ZnsISoGAh0IiRCLuTmpa/5q
3eWjgUwr3KldEJ77Sts72qSzRAD6C6RCMxnZTvcQzEjpomLLj1ID82lTrlrYl/in
MDl+i5LuDRMlgj6PQhUgV+WoRESnZ/jL2MMxA/hcFPzfDDw6A2Kzgz4wzS5FMyHM
iOCe57IN5gNeO2FAL351FHBONYQMtqeEEL82eSc53oFcLKCJf3E2yo1w6p5HB08H
IuRFwXXuD2zUkZtldBcYeAa2oA==
-----END CERTIFICATE-----"""
    problematic_private_key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpQIBAAKCAQEAwbBG0ZKbIJfT2Tvnm+jPtlw7hDWgyiFscxKoZUFqn4rzOUiT
aSAYo/Z/LyIEbtonuw5qJgZFPd7UFsC+RHGXErqgJwYM5DZpKOW7JPcO7+gKaleF
HJCIbYnuykQwqxtVyWmf9FeLmHFu/ndX2EwnzHIHIaczELBwHY4pMs0V3OUyZ56F
enmX++s0BkmmZZcJfdFcELxFXt1Qiko2vs6WMbDo0IJyoKw8dTtJf0RsbQlhhn2P
W4s5Q9NZx+FrjE/TmzvRdWKpwXO6VrZkZuA3wK698luSysZEa4pcFdVAoEPNM8jG
EnhCLnwoXsc6NSQc6y+2hCp0puXw77d4iVdzpQIDAQABAoIBAQCvQLPjftbUV+x8
++ImRTJkm/HSP7/8BOAfAvvRmq5CK7TF2TBgh4UkHq6X1BzUvJoEfBd5zmSqhcu7
xqyiO3FppemxRZ02hTEDq1J5MP6X/oomDIjJ/tEi5BJne+nZeMNXmjX8HZaW2dSH
dS7L7KR6LZbcUXA4Ip1fcLlAWSb2Fe0bcuSLPaZZSmiA1Q3B/Q6nIOqPXDWq1/yz
Vs7doSfniAt8CQse+NeWybevAHhaLjHIbqtvmAqmq91ehEiy87Cyj9VA5l4ggM8n
O6DcmjSaiXfkLgJlrMQ50Ddxoqf35pf+vzebwFdYmyt3fGlIP1OaeVsfIGbkNFZG
NQkdjEwhAoGBAObDqy8HMv070U+EXSdbv2x1A1glkA2ZUI1Ki+zXIrNV8ohZ4w71
/v2UsAAXxTCtx28EMFo923dHGk9OXM3EhmyNqYBRX97rB5V7Gt5FxmJs75punYaB
IfMvo83Hn8mrBUUb74pQhhJ2TVVv/N3nefuElys6lMwyVgUBsu0xPt1pAoGBANbe
qKouEl+lKdhfABbLCsgCp5yXhFEgNMuGArj5Op/mw/RWOYs4TuN35WmzpmsQZ2PD
+cr+/oN+eJ7zgyStDJmMkeG4vtUVJ5F4wWFWgwgY7zU1J3tu0e/EvgaaLkqWtLRE
xGJ0zc0qHQdOGGxnQPUy49yvMsdrVwHT/RQiJdDdAoGAAnxlIbKQKA426QZiAoSI
gWCZUp/E94CJT5xX+YsvwoLQhAuD2Ktpvc2WP8oBw857cYS4CKDV9mj7rZMIiObv
E8hK5Sj7QWmCwWd8GJzj0DegNSev5r0JYpdGyna2D/QZsG7mm7TWXOiNWLhGHxXZ
SI5bGoodBD4ekxs7lDaNmNECgYEAoVVd3ynosdgZq1TphDPATJ1xrKo3t5IvEgH1
WV4JHrbuuy9i1Z3Z3gHQR6WUdx9CAi7MCBeekq0LdI3zEj69Dy30+z70Spovs5Kv
4J5MlG/kbFcU5iE3kIhxBhQOXgL6e8CGlEaPoFTWpv2EaSC+LV2gqbsCralzEvRR
OiTJsCECgYEAzdFUEea4M6Uavsd36mBbCLAYkYvhMMYUcrebFpDFwZUFaOrNV0ju
5YkQTn0EQuwQWKcfs+Z+HRiqMmqj5RdgxQs6pCQG9nfp0uVSflZATOiweshGjn6f
wZWuZRQLPPTAdiW+drs3gz8w0u3Y9ihgvHQqFcGJ1+j6ANJ0XdE/D5Y=
-----END RSA PRIVATE KEY-----"""

    def test_ca_invalid_country(self):
        ca = self._create_ca(
            name="ImportTest error",
            certificate=self.problematic_certificate,
            private_key=self.problematic_private_key,
        )
        self.assertEqual(ca.country_code, "")

    def test_import_ca_key_validation_error(self):
        certificate = self.import_certificate
        private_key = self.import_private_key[20:]
        ca = Ca(
            name="TestCaKeyValidation", certificate=certificate, private_key=private_key
        )
        try:
            ca.full_clean()
        except ValidationError as e:
            error_msg = str(e.message_dict["private_key"][0])
            self.assertIn("Invalid private key", error_msg)
        else:
            self.fail("ValidationError not raised")

    def test_create_old_serial_ca(self):
        ca = self._create_ca(serial_number=3)
        self.assertEqual(int(ca.serial_number), 3)
        cert = ca.x509
        self.assertEqual(cert.serial_number, int(ca.serial_number))

    def test_bad_serial_number_ca(self):
        try:
            self._create_ca(serial_number="notIntegers")
        except ValidationError as e:
            self.assertEqual(
                "Serial number must be an integer",
                str(e.message_dict["serial_number"][0]),
            )

    def test_import_ca_key_with_passphrase(self):
        ca = Ca(name="ImportTest")
        ca.certificate = """-----BEGIN CERTIFICATE-----
MIICrzCCAhigAwIBAgIJANCybYj5LwUWMA0GCSqGSIb3DQEBCwUAMG8xCzAJBgNV
BAYTAklOMQwwCgYDVQQIDANhc2QxDDAKBgNVBAcMA2FzZDEMMAoGA1UECgwDYXNk
MQwwCgYDVQQLDANhc2QxDDAKBgNVBAMMA2FzZDEaMBgGCSqGSIb3DQEJARYLYXNk
QGFzZC5hc2QwHhcNMTgwODI5MjExMDQ1WhcNMTkwODI5MjExMDQ1WjBvMQswCQYD
VQQGEwJJTjEMMAoGA1UECAwDYXNkMQwwCgYDVQQHDANhc2QxDDAKBgNVBAoMA2Fz
ZDEMMAoGA1UECwwDYXNkMQwwCgYDVQQDDANhc2QxGjAYBgkqhkiG9w0BCQEWC2Fz
ZEBhc2QuYXNkMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDBuDdlU20Ydie8
tmbq2hn8Ski6aSH2IyVVMxUj3+i6QZmoJ4sZzcAMCLPIkCAxby5pP0V6/DSqjxTL
ShYy/7QMCovmj3O+23eYR/JGNAfsk6uDsWJL6OLHTNdx19mL0NioeFNEUJt14Cbz
uqUizT7UdONLer0UK4uP2sE09Eo4cQIDAQABo1MwUTAdBgNVHQ4EFgQURUEc1+ho
on8xaoSU+HU6CRkn0/owHwYDVR0jBBgwFoAURUEc1+hoon8xaoSU+HU6CRkn0/ow
DwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOBgQB2zU8qtkXVM25yrL9s
FC5oSqTky2c9KI/hwdsSronSvwaMoASgfl7UjzXlovq9FWZpNSVZ06wetkJVjq5N
Xn3APftPSmKw0J1tzUfZuvq8Z8q6uXQ4B2+BsiCkG/PwXizbKDc29yzXsXTL4+cQ
J7RrWKwDUi/GKVvqc+JjgsQ/nA==
-----END CERTIFICATE-----

        """
        ca.private_key = """-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,D7DDAD38C7462384

CUEPD7buBQqv/uipFz/tXYURNcQrY5HKU904IVsKbM233KPA6qU6IaRF6RRxxUtE
ejrmY2es9ZmU63gO/G/16E0CxzWhm3G2pOBsWHsBGGYcMpqZ842E3NoWimfQuRyO
E7TtMKW+Jdl6mzkw8s/KkSeGkGvZFKrclSN37CtkexRn4cXQkhNgPztyeRaQjIBM
SveP2qbODU+lr8g2oUjx05Ftcv1zJin85tzifJlQyaQz8ozKYtHA/RSpLEFZ19HG
mXn4Rvvai8r2zhdqfT/0/G6dABDrhQLxQhPE2MrY0hAlr7DnDrYNQQ/QyGoiAdcR
ee7QUDNfDnjzU6k/EjYPU1827/Kw8R4al8yDtVcUqfDuEsKabot+krEx4IZ5LOk9
PkcSW8UR0cIm7QE2BzQEzaZKQIpVwjSsSKm+RcFktiCKVun3Sps+GtXBr+AmF5Na
r6xeg+j9kz8lT8F5lnpFTk6c8cD8GDCRiLsFzPo652BQ24dAEPvsSbYmKwr1gEe8
tfsARqOuvSafQNzqBYFV7abFr8DFiE1Kghk6d6x2u7qVREvOh0RYHRWqsTRf4MMn
WlEnL9zfYST9Ur3gJgBOH2WHboDlQZu1k7yoLMfiGTQSQ2/xg1zS+5IWxt4tg029
B+f39N5zyDjuGFYcf3J6J4zybHmvdSAa62qxnkeDIbLz4axTU8+hNNOWxIsAh5vs
OO8quCk6DE4j4u3Yzk7810dkJtliwboQiTlitEbCjiyjkOrabIICKMte8nhylZX6
BxZA3knyYRiB0FNYSxI6YuCIqTjr0AoBvNHdkdjkv2VFomYNBd8ruA==
-----END RSA PRIVATE KEY-----
        """
        ca.passphrase = "test123"
        ca.full_clean()
        ca.save()
        self.assertIsInstance(ca.pkey, rsa.RSAPrivateKey)

    def test_import_ca_key_with_incorrect_passphrase(self):
        ca = Ca(name="ImportTest")
        ca.certificate = """-----BEGIN CERTIFICATE-----
MIICrzCCAhigAwIBAgIJANCybYj5LwUWMA0GCSqGSIb3DQEBCwUAMG8xCzAJBgNV
BAYTAklOMQwwCgYDVQQIDANhc2QxDDAKBgNVBAcMA2FzZDEMMAoGA1UECgwDYXNk
MQwwCgYDVQQLDANhc2QxDDAKBgNVBAMMA2FzZDEaMBgGCSqGSIb3DQEJARYLYXNk
QGFzZC5hc2QwHhcNMTgwODI5MjExMDQ1WhcNMTkwODI5MjExMDQ1WjBvMQswCQYD
VQQGEwJJTjEMMAoGA1UECAwDYXNkMQwwCgYDVQQHDANhc2QxDDAKBgNVBAoMA2Fz
ZDEMMAoGA1UECwwDYXNkMQwwCgYDVQQDDANhc2QxGjAYBgkqhkiG9w0BCQEWC2Fz
ZEBhc2QuYXNkMIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDBuDdlU20Ydie8
tmbq2hn8Ski6aSH2IyVVMxUj3+i6QZmoJ4sZzcAMCLPIkCAxby5pP0V6/DSqjxTL
ShYy/7QMCovmj3O+23eYR/JGNAfsk6uDsWJL6OLHTNdx19mL0NioeFNEUJt14Cbz
uqUizT7UdONLer0UK4uP2sE09Eo4cQIDAQABo1MwUTAdBgNVHQ4EFgQURUEc1+ho
on8xaoSU+HU6CRkn0/owHwYDVR0jBBgwFoAURUEc1+hoon8xaoSU+HU6CRkn0/ow
DwYDVR0TAQH/BAUwAwEB/zANBgkqhkiG9w0BAQsFAAOBgQB2zU8qtkXVM25yrL9s
FC5oSqTky2c9KI/hwdsSronSvwaMoASgfl7UjzXlovq9FWZpNSVZ06wetkJVjq5N
Xn3APftPSmKw0J1tzUfZuvq8Z8q6uXQ4B2+BsiCkG/PwXizbKDc29yzXsXTL4+cQ
J7RrWKwDUi/GKVvqc+JjgsQ/nA==
-----END CERTIFICATE-----

        """
        ca.private_key = """-----BEGIN RSA PRIVATE KEY-----
Proc-Type: 4,ENCRYPTED
DEK-Info: DES-EDE3-CBC,D7DDAD38C7462384

CUEPD7buBQqv/uipFz/tXYURNcQrY5HKU904IVsKbM233KPA6qU6IaRF6RRxxUtE
ejrmY2es9ZmU63gO/G/16E0CxzWhm3G2pOBsWHsBGGYcMpqZ842E3NoWimfQuRyO
E7TtMKW+Jdl6mzkw8s/KkSeGkGvZFKrclSN37CtkexRn4cXQkhNgPztyeRaQjIBM
SveP2qbODU+lr8g2oUjx05Ftcv1zJin85tzifJlQyaQz8ozKYtHA/RSpLEFZ19HG
mXn4Rvvai8r2zhdqfT/0/G6dABDrhQLxQhPE2MrY0hAlr7DnDrYNQQ/QyGoiAdcR
ee7QUDNfDnjzU6k/EjYPU1827/Kw8R4al8yDtVcUqfDuEsKabot+krEx4IZ5LOk9
PkcSW8UR0cIm7QE2BzQEzaZKQIpVwjSsSKm+RcFktiCKVun3Sps+GtXBr+AmF5Na
r6xeg+j9kz8lT8F5lnpFTk6c8cD8GDCRiLsFzPo652BQ24dAEPvsSbYmKwr1gEe8
tfsARqOuvSafQNzqBYFV7abFr8DFiE1Kghk6d6x2u7qVREvOh0RYHRWqsTRf4MMn
WlEnL9zfYST9Ur3gJgBOH2WHboDlQZu1k7yoLMfiGTQSQ2/xg1zS+5IWxt4tg029
B+f39N5zyDjuGFYcf3J6J4zybHmvdSAa62qxnkeDIbLz4axTU8+hNNOWxIsAh5vs
OO8quCk6DE4j4u3Yzk7810dkJtliwboQiTlitEbCjiyjkOrabIICKMte8nhylZX6
BxZA3knyYRiB0FNYSxI6YuCIqTjr0AoBvNHdkdjkv2VFomYNBd8ruA==
-----END RSA PRIVATE KEY-----
        """
        try:
            ca.passphrase = "incorrect_passphrase"
            ca.full_clean()
            ca.save()
        except ValidationError as e:
            self.assertIn("Incorrect Passphrase", str(e.message_dict["passphrase"][0]))
        else:
            self.fail("ValidationError not raised")

    def test_generate_ca_with_passphrase(self):
        ca = self._create_ca(passphrase="123")
        ca.full_clean()
        ca.save()
        self.assertIsInstance(ca.pkey, rsa.RSAPrivateKey)

    def test_datetime_to_string(self):
        generalized_datetime = datetime(2050, 1, 1, 0, 0, 0, 0)
        utc_datetime = datetime(2049, 12, 31, 0, 0, 0, 0)
        self.assertEqual(
            datetime_to_string(generalized_datetime),
            generalized_datetime.strftime(UTC_TIME),
        )
        self.assertEqual(
            datetime_to_string(utc_datetime), utc_datetime.strftime(UTC_TIME)
        )

    def test_renew(self):
        ca = self._create_ca()
        certs = [
            self._create_cert(ca=ca, name="cert1"),
            self._create_cert(ca=ca, name="cert2"),
        ]
        old_ca_cert = ca.certificate
        old_ca_key = ca.private_key
        old_ca_end = ca.validity_end
        old_certs_data = []
        for c in certs:
            old_certs_data.append(
                {
                    "cert": c.certificate,
                    "key": c.private_key,
                    "end": c.validity_end,
                    "serial": c.serial_number,
                }
            )
        ca.renew()
        ca.refresh_from_db()
        self.assertNotEqual(old_ca_cert, ca.certificate)
        self.assertNotEqual(old_ca_key, ca.private_key)
        self.assertGreater(ca.validity_end, old_ca_end)
        for i, c in enumerate(certs):
            c.refresh_from_db()
            old = old_certs_data[i]

            self.assertNotEqual(old["cert"], c.certificate)
            self.assertNotEqual(old["key"], c.private_key)
            self.assertNotEqual(old["serial"], c.serial_number)
            self.assertGreater(c.validity_end, old["end"])

    def test_ca_common_name_length(self):
        common_name = "a" * 65
        with self.assertRaises(ValidationError) as cm:
            self._create_ca(common_name=common_name)

        msg = (
            f"Ensure this value has at most 64 characters (it has {len(common_name)})."
        )
        message_dict = cm.exception.message_dict
        self.assertIn("common_name", message_dict)
        self.assertEqual(message_dict["common_name"][0], msg)

    def test_ca_without_key_length_and_digest_algo(self):
        try:
            self._create_ca(key_length="", digest="")
        except ValidationError as e:
            self.assertIn("key_length", e.error_dict)
            self.assertIn("digest", e.error_dict)
        except Exception as e:
            self.fail(f"Got exception: {e}")
        else:
            self.fail("ValidationError not raised as expected")

    def test_renewal_serial_sync(self):
        ca = self._create_ca()
        cert = self._create_cert(ca=ca)
        ca.renew()
        cert.refresh_from_db()
        cert_obj = x509.load_pem_x509_certificate(cert.certificate.encode())
        pem_serial = cert_obj.serial_number
        self.assertEqual(int(cert.serial_number), pem_serial)

    def test_ca_ecdsa_full_lifecycle(self):
        curves_to_test = [
            ("256", ec.SECP256R1, hashes.SHA256()),
            ("384", ec.SECP384R1, hashes.SHA384()),
            ("521", ec.SECP521R1, hashes.SHA512()),
        ]
        for length, curve_class, digest in curves_to_test:
            with self.subTest(key_length=length):
                priv_key = ec.generate_private_key(curve_class())
                key_pem = priv_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode("utf-8")
                now = datetime.now(dt_timezone.utc)
                subject = issuer = x509.Name(
                    [x509.NameAttribute(NameOID.COMMON_NAME, "test")]
                )
                cert = (
                    x509.CertificateBuilder()
                    .subject_name(subject)
                    .issuer_name(issuer)
                    .public_key(priv_key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now)
                    .not_valid_after(now + timedelta(days=10))
                    .sign(priv_key, digest)
                )
                cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
                ca = Ca(
                    name=f"EC-{length}",
                    certificate=cert_pem,
                    private_key=key_pem,
                    key_length=length,
                )
                ca.full_clean()
                ca.save()
                self.assertEqual(ca.key_length, length)
                self.assertIsInstance(ca.pkey, ec.EllipticCurvePrivateKey)
                gen_ca = Ca(
                    name=f"Gen-EC-{length}",
                    key_length=length,
                )
                gen_ca.full_clean()
                gen_ca.save()
                self.assertIsInstance(gen_ca.pkey, ec.EllipticCurvePrivateKey)
                original_cert = gen_ca.certificate
                original_key = gen_ca.private_key
                gen_ca.renew()
                gen_ca.refresh_from_db()
                self.assertEqual(gen_ca.key_length, length)
                self.assertNotEqual(gen_ca.private_key, original_key)
                self.assertNotEqual(original_cert, gen_ca.certificate)
