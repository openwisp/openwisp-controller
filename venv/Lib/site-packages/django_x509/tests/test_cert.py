from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.oid import NameOID
from django.core.exceptions import ValidationError
from django.test import TestCase
from openwisp_utils.tests import AssertNumQueriesSubTestMixin

from .. import settings as app_settings
from . import Ca, Cert, TestX509Mixin


class TestCert(AssertNumQueriesSubTestMixin, TestX509Mixin, TestCase):
    """
    tests for Cert model
    """

    import_certificate = """
-----BEGIN CERTIFICATE-----
MIIDNjCCAh6gAwIBAgIDAeJAMA0GCSqGSIb3DQEBCwUAMHcxEzARBgNVBAMMCmlt
cG9ydHRlc3QxCzAJBgNVBAYTAlVTMQswCQYDVQQIDAJDQTEWMBQGA1UEBwwNU2Fu
IEZyYW5jaXNjbzENMAsGA1UECgwEQUNNRTEfMB0GCSqGSIb3DQEJARYQY29udGFj
dEBhY21lLmNvbTAeFw0yNjAxMTcxNTUxNTVaFw0zNjAxMTUxNTUxNTVaMAAwggEi
MA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQC5NNAOi6Fqj+1bDT/PXSqnB6qc
1F1j9DYvGw4/YBZTDvyII66rQQ34/SgEkNhYH5f5Q7xxEaZHD29TGUE3wj+sps8L
WrgJd6shzIHYArZNQ21ZIy93aTZT87KznCBcsr0pFr6yHa0rVAug/x4dtxhq2wGA
ESdwkzbTPP3yXjASLt20CMBQP7ZSIVmJSO/ZJ+ukdFz7psUnZhpXcav97lLsi8+A
yXaRDSBkDOjiw0p0JO6syOxX7CNohNFJstiLc20A2YahN00RfjSRq92+3iLUHzVW
RpiQs2EA3lg4SSre3dthqvWTNm48Sdy1x5AgipRHipaa/XSiAVbBkHwn/g1rAgMB
AAGjQjBAMB0GA1UdDgQWBBSgr3fucGsd3A1fX0A2I0Ai9yy5ajAfBgNVHSMEGDAW
gBSufESUfqH1WZBlgcb5oYdK6ENrIzANBgkqhkiG9w0BAQsFAAOCAQEACRNSrr20
rpl8WSo+hzavnE6jzd3S4PYl4IU3cY03C/1uJ7ode00TOpq0LGIC5QToxcUNOqmb
AU+JINaEXXy5jyud/p/SzsN1jXfP1MQcvTyL4thxcUftXYeoFaq+u8YgRFbuzCeD
cnn0S+QXNKIOkASEEuEWRaMjWFDL17CNhEsW2HXV3MOhZv5L9ft5ua007LfDGTk9
1Y+RQ+6/nAn9K0zRoKebnWWVWfgmUDCRYronbn13BU0elecMGqcsZzq+zTo8ePDG
+Hx97JA9mJhRsGQkIAYk24SKF9mOPUb2MCUHW41UHa09yUlKENgshwR5zMksioZ6
CdicXI48yT96WQ==
-----END CERTIFICATE-----
"""
    import_private_key = """
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC5NNAOi6Fqj+1b
DT/PXSqnB6qc1F1j9DYvGw4/YBZTDvyII66rQQ34/SgEkNhYH5f5Q7xxEaZHD29T
GUE3wj+sps8LWrgJd6shzIHYArZNQ21ZIy93aTZT87KznCBcsr0pFr6yHa0rVAug
/x4dtxhq2wGAESdwkzbTPP3yXjASLt20CMBQP7ZSIVmJSO/ZJ+ukdFz7psUnZhpX
cav97lLsi8+AyXaRDSBkDOjiw0p0JO6syOxX7CNohNFJstiLc20A2YahN00RfjSR
q92+3iLUHzVWRpiQs2EA3lg4SSre3dthqvWTNm48Sdy1x5AgipRHipaa/XSiAVbB
kHwn/g1rAgMBAAECggEAOFlAqgRCnrzejvLXhLxIY1xaRO/54BTnvWpCafbOpAOt
wq/0j0cyPJytZcI6CInIP78joNUpXXptOP+4j4HqxJlV6hL2Zm8B4r0pjjK5C4Xl
yZaCdRbOQDmnl6z7TajWE5/HckLEMqgWB6xHGexgofYzHSda9A3eQuPOMcUFZCpX
H//sZPCOgkidObZ/jNQ3pH1A5JJ5BdZtz3BFvHkv+OHjEY8nNPbMuylMiOSbyLDZ
zrF9ghSJYp1KpbxdojkzVYJSrZ9P2bDX+JJXqrmQ62LbPbRtETRxHc+VA4u4ZhS/
/GC20bXkuoOLJg0LJw1R4qEJ8o3g9XVni/cBUzR6ZQKBgQD9nQYKULSG8vlFP711
uaP2TQhaCMEPESzg1SS6H3lLBH5NYdG5gY8omoNBzoIZk2XHiaDsTFpGMsPZrufP
BvN5VQukaYYe8jPBfq5ktlSbAkvQRVmuFlFT+bA1n/5jZCQyAd1Un8aJBYr+AdNl
BzpCQUeTmP069OO50V4hjbbBJQKBgQC68v2YlGxpOBlngscKGZzSNjcxrZG+erul
ZTt899waDaJEH3cxUjPcEZbAjin7gmsDehWN+kZ5kn4rd3+9M89SH63cd2lQq+fb
pckOH5yvKjRsNCcwG5mlNcAkAWnbOL6ajNbdHVwNwPB4f4fEdsflTkuHgoUWfLB4
UtY5oTu3TwKBgFWgYXy0GO+DM5Qk3CPWRLyQ76PuVrhulRdn/1lz7PDeGIKp5zRZ
wOr1mCFsxtI5yOBg4FtHwCb5VtS1UAC/GQ87Ho4pLqZeIglPazQHt3MKiGxOLeQw
Fs9iexLv7OTD19CmfoLm2xJCM9Zk6Wmv0gSyo6b6vWzdZ9HCFaUAgtadAoGBAKNg
3BNOEvhZWIpHlh7Th2OGkfHOWEJ5DChdMgHisu3p4FdckFQAHOZEUNTy6OmubktZ
lCDCCnkQd0cRZgc5kgOZP94eVWF0+mnQlsbLBalnXuz5Hw5B8KKbONG+kn5NNvXm
A5i1oc87QGxuN36Qt91D8Wn5vMmMKsTcz+8JYyCtAoGBAK2vieDw6rD8k4UAp4Nn
hYMtcPeVKNPcZxGWzh9abX0YcW02F6kP9xd0Mlv9AhCPl2xwoSB9y1WoOlCzvijq
0pl8/DG+QHhnd0h362CaOuzpuH7863QhoAyIqVejED+XWkmYwjYK3CUqSRnnqFK/
v/Qdu78ntVYDbDKuoaWE3uPa
-----END PRIVATE KEY-----

"""
    import_ca_certificate = """
-----BEGIN CERTIFICATE-----
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
-----END CERTIFICATE-----
"""
    import_ca_private_key = """
-----BEGIN PRIVATE KEY-----
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
-----END PRIVATE KEY-----

"""

    def test_new(self):
        with self.assertNumQueries(3):
            cert = self._create_cert()
        self.assertNotEqual(cert.certificate, "")
        self.assertNotEqual(cert.private_key, "")
        x509_obj = cert.x509
        self.assertEqual(x509_obj.serial_number, int(cert.serial_number))
        # ensure version is 3
        self.assertEqual(x509_obj.version, x509.Version.v3)

        def get_attr(name_obj, oid):
            attrs = name_obj.get_attributes_for_oid(oid)
            return str(attrs[0].value) if attrs else ""

        # check subject
        mapping = {
            NameOID.COUNTRY_NAME: cert.country_code,
            NameOID.STATE_OR_PROVINCE_NAME: cert.state,
            NameOID.LOCALITY_NAME: cert.city,
            NameOID.ORGANIZATION_NAME: cert.organization_name,
            NameOID.EMAIL_ADDRESS: cert.email,
            NameOID.COMMON_NAME: cert.common_name,
        }
        for oid, expected_val in mapping.items():
            self.assertEqual(get_attr(x509_obj.subject, oid), expected_val)
        # check issuer
        self.assertEqual(x509_obj.issuer, cert.ca.x509.subject)
        self.assertEqual(
            get_attr(x509_obj.issuer, NameOID.COMMON_NAME), cert.ca.common_name
        )
        # check signature
        cert._verify_ca()
        # basic constraints
        ext = x509_obj.extensions.get_extension_for_class(x509.BasicConstraints)
        self.assertFalse(ext.critical)
        self.assertFalse(ext.value.ca)

    def test_x509_property(self):
        cert = self._create_cert()
        cert_from_pem = x509.load_pem_x509_certificate(cert.certificate.encode())
        self.assertEqual(cert.x509.subject, cert_from_pem.subject)
        self.assertEqual(cert.x509.issuer, cert_from_pem.issuer)

    def test_x509_property_none(self):
        self.assertIsNone(Cert().x509)

    def test_pkey_property(self):
        cert = self._create_cert()
        self.assertIsInstance(cert.pkey, rsa.RSAPrivateKey)

    def test_pkey_property_none(self):
        self.assertIsNone(Cert().pkey)

    def test_default_validity_end(self):
        cert = Cert()
        self.assertEqual(cert.validity_end.year, datetime.now().year + 1)

    def test_default_validity_start(self):
        cert = Cert()
        expected = datetime.now() - timedelta(days=1)
        self.assertEqual(cert.validity_start.year, expected.year)
        self.assertEqual(cert.validity_start.month, expected.month)
        self.assertEqual(cert.validity_start.day, expected.day)
        self.assertEqual(cert.validity_start.hour, 0)
        self.assertEqual(cert.validity_start.minute, 0)
        self.assertEqual(cert.validity_start.second, 0)

    def test_import_cert(self):
        ca = Ca(name="ImportTest")
        ca.certificate = self.import_ca_certificate
        ca.private_key = self.import_ca_private_key
        ca.full_clean()
        ca.save()
        cert = Cert(
            name="ImportCertTest",
            ca=ca,
            certificate=self.import_certificate,
            private_key=self.import_private_key,
        )
        cert.full_clean()
        cert.save()
        x509_obj = cert.x509
        # verify attributes
        self.assertEqual(x509_obj.serial_number, 123456)
        # verify issuer (using CA subject for comparison)
        self.assertEqual(x509_obj.issuer, ca.x509.subject)
        # verify field attributes
        self.assertEqual(cert.key_length, "2048")
        self.assertEqual(cert.digest, "sha256")
        self.assertEqual(int(cert.serial_number), 123456)

        self.assertEqual(cert.country_code, "")
        self.assertEqual(cert.common_name, "")
        start = datetime(2026, 1, 17, 15, 51, 55, tzinfo=dt_timezone.utc)
        end = datetime(2036, 1, 15, 15, 51, 55, tzinfo=dt_timezone.utc)
        self.assertEqual(cert.validity_start, start)
        self.assertEqual(cert.validity_end, end)
        # ensure version is 3
        self.assertEqual(x509_obj.version, x509.Version.v3)
        cert.delete()
        # test auto name
        cert = Cert(
            certificate=self.import_certificate,
            private_key=self.import_private_key,
            ca=ca,
        )
        cert.full_clean()
        cert.save()
        self.assertEqual(cert.name, "123456")

    def test_import_private_key_empty(self):
        ca = self._create_ca()
        cert = Cert(name="ImportTest", ca=ca)
        cert.certificate = self.import_certificate
        with self.assertRaises(ValidationError) as cm:
            cert.full_clean()
        self.assertIn("importing an existing certificate", str(cm.exception))

    def test_import_wrong_ca(self):
        ca = self._create_ca()
        # test auto name
        cert = Cert(
            certificate=self.import_certificate,
            private_key=self.import_private_key,
            ca=ca,
        )
        with self.assertRaises(ValidationError) as cm:
            cert.full_clean()
        self.assertIn("The Certificate Issuer does not match", str(cm.exception))

    def test_keyusage(self):
        cert = self._create_cert()
        ext = cert.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertFalse(ext.critical)
        self.assertTrue(ext.value.digital_signature)
        self.assertTrue(ext.value.key_encipherment)

    def test_keyusage_critical(self):
        setattr(app_settings, "CERT_KEYUSAGE_CRITICAL", True)
        cert = self._create_cert()
        ext = cert.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertTrue(ext.critical)
        setattr(app_settings, "CERT_KEYUSAGE_CRITICAL", False)

    def test_keyusage_value(self):
        setattr(app_settings, "CERT_KEYUSAGE_VALUE", "digitalSignature")
        cert = self._create_cert()
        ext = cert.x509.extensions.get_extension_for_class(x509.KeyUsage)
        self.assertTrue(ext.value.digital_signature)
        self.assertFalse(ext.value.key_encipherment)
        setattr(
            app_settings, "CERT_KEYUSAGE_VALUE", "digitalSignature, keyEncipherment"
        )

    def test_subject_key_identifier(self):
        cert = self._create_cert()
        ext = cert.x509.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        self.assertFalse(ext.critical)
        expected_ski = x509.SubjectKeyIdentifier.from_public_key(cert.pkey.public_key())
        self.assertEqual(ext.value, expected_ski)

    def test_authority_key_identifier(self):
        cert = self._create_cert()
        ext = cert.x509.extensions.get_extension_for_class(x509.AuthorityKeyIdentifier)
        self.assertFalse(ext.critical)
        ca_ski = cert.ca.x509.extensions.get_extension_for_class(
            x509.SubjectKeyIdentifier
        )
        self.assertEqual(ext.value.key_identifier, ca_ski.value.digest)

    def test_extensions(self):
        extensions = [
            {"name": "nsCertType", "critical": False, "value": "client"},
            {
                "name": "extendedKeyUsage",
                "critical": True,  # critical just for testing purposes
                "value": "clientAuth",
            },
        ]
        cert = self._create_cert(extensions=extensions)
        x509_obj = cert.x509
        ns_oid = x509.ObjectIdentifier("2.16.840.1.113730.1.1")
        e1 = cert.x509.extensions.get_extension_for_oid(ns_oid)
        self.assertFalse(e1.critical)
        self.assertEqual(e1.value.value, b"\x03\x02\x07\x80")
        e2 = x509_obj.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
        self.assertTrue(e2.critical)
        self.assertIn(x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH, e2.value)

    def test_extensions_error1(self):
        extensions = {}
        try:
            self._create_cert(extensions=extensions)
        except ValidationError as e:
            msg = e.message_dict.get("__all__", [str(e)])[0]
            self.assertIn("Extension format invalid", str(msg))
        else:
            self.fail("ValidationError not raised")

    def test_extensions_error2(self):
        extensions = [{"wrong": "wrong"}]
        try:
            self._create_cert(extensions=extensions)
        except ValidationError as e:
            msg = e.message_dict.get("__all__", [str(e)])[0]
            self.assertIn("Extension format invalid", str(msg))
        else:
            self.fail("ValidationError not raised")

    def test_revoke(self):
        cert = self._create_cert()
        self.assertFalse(cert.revoked)
        self.assertIsNone(cert.revoked_at)
        cert.revoke()
        self.assertTrue(cert.revoked)
        self.assertIsNotNone(cert.revoked_at)

    def test_x509_text(self):
        cert = self._create_cert()
        text = cert.x509_text
        self.assertIsNotNone(text)
        # Verify OpenSSL-style text output format
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
        self.assertIn(cert.common_name, text)
        self.assertIn("Subject Public Key Info:", text)
        self.assertIn("X509v3 extensions:", text)
        self.assertIn("X509v3 Basic Constraints:", text)
        self.assertIn("CA:FALSE", text)
        new_cert = Cert()
        self.assertIsNone(new_cert.x509_text)

    def test_get_subject_None_attrs(self):
        ca = self._create_ca()
        cert = Cert(name="test", ca=ca, common_name="test")
        subject = cert._get_subject()
        cn_attrs = subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        self.assertEqual(len(cn_attrs), 1)
        self.assertEqual(cn_attrs[0].value, "test")
        self.assertEqual(len(subject.get_attributes_for_oid(NameOID.COUNTRY_NAME)), 0)
        self.assertEqual(
            len(subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)), 0
        )
        cert.country_code = "IT"
        subject_updated = cert._get_subject()
        self.assertEqual(
            len(subject_updated.get_attributes_for_oid(NameOID.COUNTRY_NAME)), 1
        )
        self.assertEqual(
            subject_updated.get_attributes_for_oid(NameOID.COUNTRY_NAME)[0].value, "IT"
        )

    def test_cert_create(self):
        ca = Ca(name="Test CA")
        ca.full_clean()
        ca.save()

        Cert.objects.create(ca=ca, common_name="TestCert1", name="TestCert1")

    def test_import_cert_validation_error(self):
        certificate = self.import_certificate[20:]
        private_key = self.import_private_key
        ca = self._create_ca()
        try:
            cert = Cert(
                name="TestCertValidation",
                ca=ca,
                certificate=certificate,
                private_key=private_key,
            )
            cert.full_clean()
        except ValidationError as e:
            error_msg = str(e.message_dict["certificate"][0])
            self.assertIn("Invalid certificate", error_msg)
        else:
            self.fail("ValidationError not raised")

    def test_import_key_validation_error(self):
        certificate = self.import_certificate
        private_key = self.import_private_key[20:]
        ca = self._create_ca()
        try:
            cert = Cert(
                name="TestKeyValidation",
                ca=ca,
                certificate=certificate,
                private_key=private_key,
            )
            cert.full_clean()
        except ValidationError as e:
            error_msg = str(e.message_dict["private_key"][0])
            self.assertIn("Invalid private key", error_msg)
        else:
            self.fail("ValidationError not raised")

    def test_create_old_serial_certificate(self):
        cert = self._create_cert(serial_number=3)
        self.assertEqual(int(cert.serial_number), 3)
        x509_obj = cert.x509
        self.assertEqual(x509_obj.serial_number, 3)

    def test_bad_serial_number_cert(self):
        try:
            self._create_cert(serial_number="notIntegers")
        except ValidationError as e:
            self.assertEqual(
                "Serial number must be an integer",
                str(e.message_dict["serial_number"][0]),
            )

    def test_serial_number_clash(self):
        ca = Ca(name="TestSerialClash")
        ca.certificate = self.import_ca_certificate
        ca.private_key = self.import_ca_private_key
        ca.save()
        cert = self._create_cert(serial_number=123456, ca=ca)
        cert.full_clean()
        cert.save()
        _cert = Cert(
            name="TestClash",
            ca=ca,
            certificate=self.import_certificate,
            private_key=self.import_private_key,
        )
        try:
            _cert.full_clean()
        except ValidationError as e:
            self.assertEqual(
                "Certificate with this CA and Serial number already exists.",
                str(e.message_dict["__all__"][0]),
            )
        else:
            self.fail("ValidationError not raised for serial clash")

    def test_import_cert_with_passphrase(self):
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

    def test_generate_ca_with_passphrase(self):
        ca = self._create_ca(passphrase="123")
        ca.full_clean()
        ca.save()
        self.assertIsInstance(ca.pkey, rsa.RSAPrivateKey)

    def test_renew(self):
        cert = self._create_cert()
        old_cert = cert.certificate
        old_key = cert.private_key
        old_end = cert.validity_end
        old_serial_number = cert.serial_number
        ca = cert.ca
        old_ca_cert = ca.certificate
        old_ca_key = ca.private_key
        old_ca_end = ca.validity_end
        old_ca_serial_number = str(cert.ca.serial_number)
        cert.renew()
        self.assertNotEqual(old_cert, cert.certificate)
        self.assertNotEqual(old_key, cert.private_key)
        self.assertGreater(cert.validity_end, old_end)
        self.assertNotEqual(old_serial_number, cert.serial_number)
        ca = cert.ca
        ca.refresh_from_db()
        self.assertEqual(old_ca_cert, ca.certificate)
        self.assertEqual(old_ca_key, ca.private_key)
        self.assertEqual(old_ca_end, ca.validity_end)
        self.assertEqual(old_ca_serial_number, ca.serial_number)

    def test_cert_common_name_length(self):
        common_name = "a" * 65
        with self.assertRaises(ValidationError) as context_manager:
            self._create_cert(common_name=common_name)
        msg = (
            f"Ensure this value has at most 64 characters (it has {len(common_name)})."
        )
        message_dict = context_manager.exception.message_dict
        self.assertIn("common_name", message_dict)
        self.assertEqual(message_dict["common_name"][0], msg)

    def test_cert_ecdsa_full_lifecycle(self):
        curves_to_test = [
            ("256", ec.SECP256R1, hashes.SHA256()),
            ("384", ec.SECP384R1, hashes.SHA384()),
            ("521", ec.SECP521R1, hashes.SHA512()),
        ]
        for length, curve_class, digest in curves_to_test:
            with self.subTest(key_length=length):
                ca = Ca(name=f"CA-{length}", key_length=length)
                ca.full_clean()
                ca.save()
                priv_key = ec.generate_private_key(curve_class())
                key_pem = priv_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode("utf-8")
                now = datetime.now(dt_timezone.utc)
                subject = x509.Name(
                    [x509.NameAttribute(NameOID.COMMON_NAME, "test-cert")]
                )
                cert = (
                    x509.CertificateBuilder()
                    .subject_name(subject)
                    .issuer_name(ca.x509.subject)
                    .public_key(priv_key.public_key())
                    .serial_number(x509.random_serial_number())
                    .not_valid_before(now)
                    .not_valid_after(now + timedelta(days=10))
                    .sign(ca.pkey, digest)
                )
                cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
                entity_cert = Cert(
                    name=f"EC-{length}-Import",
                    ca=ca,
                    certificate=cert_pem,
                    private_key=key_pem,
                    key_length=length,
                )
                entity_cert.full_clean()
                entity_cert.save()
                self.assertEqual(entity_cert.key_length, length)
                gen_cert = Cert(
                    name=f"Gen-EC-{length}",
                    ca=ca,
                    key_length=length,
                )
                gen_cert.full_clean()
                gen_cert.save()
                self.assertIsInstance(gen_cert.pkey, ec.EllipticCurvePrivateKey)
                original_pem = gen_cert.certificate
                gen_cert.renew()
                gen_cert.refresh_from_db()
                self.assertNotEqual(original_pem, gen_cert.certificate)
