import json
import uuid
from copy import deepcopy
from io import StringIO
from unittest.mock import Mock, call, patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import models
from django.db.transaction import atomic
from django.test import TestCase
from django.test.testcases import TransactionTestCase
from netjsonconfig import OpenWrt
from swapper import load_model

from openwisp_utils.tests import catch_signal

from .. import settings as app_settings
from .. import tasks
from ..base.base import logger as base_config_logger
from ..base.cache import CacheDependency
from ..handlers import invalidate_devicegroup_cache_change_handler
from ..signals import config_backend_changed, config_modified, config_status_changed
from .utils import (
    CreateConfigTemplateMixin,
    CreateDeviceGroupMixin,
    TestVpnX509Mixin,
    TestWireguardVpnMixin,
)

Config = load_model("config", "Config")
Device = load_model("config", "Device")
DeviceGroup = load_model("config", "DeviceGroup")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")
Template = load_model("config", "Template")
Vpn = load_model("config", "Vpn")
Ca = load_model("django_x509", "Ca")
Cert = load_model("django_x509", "Cert")


class TestConfig(
    CreateConfigTemplateMixin,
    CreateDeviceGroupMixin,
    TestVpnX509Mixin,
    TestCase,
):
    """
    tests for Config model
    """

    fixtures = ["test_templates"]
    maxDiff = None

    def test_str(self):
        c = Config()
        self.assertEqual(str(c), str(c.pk))
        c = Config(device=Device(name="test"))
        self.assertEqual(str(c), "test")

    def test_config_not_none(self):
        c = Config(
            device=self._create_device(), backend="netjsonconfig.OpenWrt", config=None
        )
        c.full_clean()
        self.assertEqual(c.config, {})

    def test_backend_class(self):
        c = Config(backend="netjsonconfig.OpenWrt")
        self.assertIs(c.backend_class, OpenWrt)

    def test_backend_instance(self):
        config = {"general": {"hostname": "config"}}
        c = Config(backend="netjsonconfig.OpenWrt", config=config)
        self.assertIsInstance(c.backend_instance, OpenWrt)

    def test_error_reason_clean(self):
        config = self._create_config(organization=self._get_org())
        config.error_reason = "e" * 1030
        config.full_clean()
        self.assertEqual(len(config.error_reason), 1024)
        self.assertEqual(config.error_reason[1013:], "[truncated]")

    def test_error_reason_status_error_modified(self):
        error_reason = "Configuration cannot be applied."
        config = self._create_config(organization=self._get_org())
        self.assertEqual(config.status, "modified")
        self.assertEqual(config.error_reason, "")

        with self.subTest("Test configuration status changes to modified"):
            config.set_status_error(reason=error_reason)
            self.assertEqual(config.status, "error")
            self.assertEqual(config.error_reason, error_reason)
            config.set_status_modified()
            self.assertEqual(config.status, "modified")
            self.assertEqual(config.error_reason, "")

        with self.subTest("Test configuration status changes to applied"):
            config.set_status_error(reason=error_reason)
            self.assertEqual(config.status, "error")
            self.assertEqual(config.error_reason, error_reason)
            config.set_status_applied()
            self.assertEqual(config.status, "applied")
            self.assertEqual(config.error_reason, "")

    @patch.object(app_settings, "DSA_DEFAULT_FALLBACK", False)
    @patch.object(
        app_settings,
        "DSA_OS_MAPPING",
        {
            "netjsonconfig.OpenWrt": {
                ">=21.02": [r"MyCustomFirmware 2.1(.*)"],
                "<21.02": [r"MyCustomFirmware 2.0(.*)"],
            }
        },
    )
    def test_backend_openwrt_different_versions(self):
        with self.subTest("DSA enabled OpenWrt firmware"):
            c = Config(
                backend="netjsonconfig.OpenWrt",
                device=Device(name="test", os="OpenWrt 21.02.2 r16495-bf0c965af0"),
            )
            self.assertIsInstance(c.backend_instance, OpenWrt)
            self.assertEqual(c.backend_instance.dsa, True)

        with self.subTest("DSA disabled OpenWrt Firmware"):
            c = Config(
                backend="netjsonconfig.OpenWrt",
                device=Device(name="test", os="OpenWrt 19.02.2 r16495-bf0c965af0"),
            )
            self.assertIsInstance(c.backend_instance, OpenWrt)
            self.assertEqual(c.backend_instance.dsa, False)

        with self.subTest("DSA enabled custom firmware"):
            c = Config(
                backend="netjsonconfig.OpenWrt",
                device=Device(name="test", os="MyCustomFirmware 2.1.2"),
            )
            self.assertIsInstance(c.backend_instance, OpenWrt)
            self.assertEqual(c.backend_instance.dsa, True)

        with self.subTest("DSA disabled custom firmware"):
            c = Config(
                backend="netjsonconfig.OpenWrt",
                device=Device(name="test", os="MyCustomFirmware 2.0.1"),
            )
            self.assertIsInstance(c.backend_instance, OpenWrt)
            self.assertEqual(c.backend_instance.dsa, False)

        with self.subTest("Device os field is empty"):
            c = Config(
                backend="netjsonconfig.OpenWrt",
                device=Device(name="test", os=""),
            )
            self.assertIsInstance(c.backend_instance, OpenWrt)
            self.assertEqual(c.backend_instance.dsa, False)

    def test_netjson_validation(self):
        config = {"interfaces": {"invalid": True}}
        c = Config(
            device=self._create_device(), backend="netjsonconfig.OpenWrt", config=config
        )
        # ensure django ValidationError is raised
        try:
            c.full_clean()
        except ValidationError as e:
            self.assertIn("Invalid configuration", e.message_dict["__all__"][0])
        else:
            self.fail("ValidationError not raised")

    def test_json(self):
        dhcp = Template.objects.get(name="dhcp")
        radio = Template.objects.get(name="radio0")
        c = self._create_config(
            organization=self._get_org(), config={"general": {"hostname": "json-test"}}
        )
        c.templates.add(dhcp)
        c.templates.add(radio)
        full_config = {
            "general": {"hostname": "json-test"},
            "interfaces": [
                {
                    "name": "eth0",
                    "type": "ethernet",
                    "addresses": [{"proto": "dhcp", "family": "ipv4"}],
                }
            ],
            "radios": [
                {
                    "name": "radio0",
                    "phy": "phy0",
                    "driver": "mac80211",
                    "protocol": "802.11n",
                    "channel": 11,
                    "channel_width": 20,
                    "tx_power": 8,
                    "country": "IT",
                }
            ],
        }
        del c.backend_instance
        self.assertDictEqual(c.json(dict=True), full_config)
        json_string = c.json()
        self.assertIn("json-test", json_string)
        self.assertIn("eth0", json_string)
        self.assertIn("radio0", json_string)

    def test_m2m_validation(self):
        # if config and template have a conflicting non-unique item
        # that violates the schema, the system should not allow
        # the assignment and raise an exception
        config = {"files": [{"path": "/test", "mode": "0644", "contents": "test"}]}
        config_copy = deepcopy(config)
        t = Template(name="files", backend="netjsonconfig.OpenWrt", config=config)
        t.full_clean()
        t.save()
        c = self._create_config(organization=self._get_org(), config=config_copy)
        with atomic():
            try:
                c.templates.add(t)
            except ValidationError:
                self.fail("ValidationError raised!")
        t.config["files"][0]["path"] = "/test2"
        t.full_clean()
        t.save()
        c.templates.add(t)

    def test_checksum(self):
        c = self._create_config(organization=self._get_org())
        self.assertEqual(len(c.checksum), 32)

    def test_get_cached_checksum(self):
        c = self._create_config(organization=self._get_org())

        with self.subTest("check cache set"):
            with patch("django.core.cache.cache.set") as mocked_set:
                checksum = c.get_cached_checksum()
                self.assertEqual(len(checksum), 32)
                mocked_set.assert_called_once()

        with self.subTest("check cache get"):
            with patch(
                "django.core.cache.cache.get", return_value=checksum
            ) as mocked_get:
                self.assertEqual(len(c.get_cached_checksum()), 32)
                mocked_get.assert_called_once()

        with self.subTest("ensure fresh checksum is calculated when cache is clear"):
            with patch.object(base_config_logger, "debug") as mocked_debug:
                c.get_cached_checksum.invalidate(c)
                self.assertEqual(len(c.get_cached_checksum()), 32)
                mocked_debug.assert_not_called()

        with self.subTest(
            "ensure fresh checksum is NOT calculated when cache is present"
        ):
            with patch.object(base_config_logger, "debug") as mocked_debug:
                self.assertEqual(len(c.get_cached_checksum()), 32)
                mocked_debug.assert_not_called()

        with self.subTest("ensure cache invalidation works"):
            with patch.object(base_config_logger, "debug") as mocked_debug:
                old_checksum = c.checksum
                c.config["general"]["timezone"] = "Europe/Rome"
                c.full_clean()
                c.save()
                del c.backend_instance
                self.assertNotEqual(c.checksum, old_checksum)
                self.assertEqual(c.get_cached_checksum(), c.checksum)
                mocked_debug.assert_called_once()

        with self.subTest("test cache invalidation when config templates are changed"):
            with patch.object(base_config_logger, "debug") as mocked_debug:
                old_checksum = c.checksum
                template = self._create_template()
                c.templates.add(template)
                del c.backend_instance
                self.assertNotEqual(c.checksum, old_checksum)
                self.assertEqual(c.get_cached_checksum(), c.checksum)
                mocked_debug.assert_called_once()

        with self.subTest("cache invalidation works when config is deactivated"):
            with patch.object(base_config_logger, "debug") as mocked_debug:
                old_checksum = c.checksum
                c.deactivate()
                del c.backend_instance
                self.assertNotEqual(c.checksum, old_checksum)
                self.assertEqual(c.get_cached_checksum(), c.checksum)
                mocked_debug.assert_called_once()

    def test_backend_import_error(self):
        """
        see issue #5
        https://github.com/openwisp/django-netjsonconfig/issues/5
        """
        c = Config(device=self._create_device())
        with self.assertRaises(ValidationError):
            c.full_clean()
        c.backend = "wrong"
        with self.assertRaises(ValidationError):
            c.full_clean()

    def test_default_status(self):
        c = Config()
        self.assertEqual(c.status, "modified")

    def test_status_modified_after_change(self):
        c = self._create_config(organization=self._get_org(), status="applied")
        self.assertEqual(c.status, "applied")
        c.refresh_from_db()
        c.config = {"general": {"description": "test"}}
        c.full_clean()
        c.save()
        self.assertEqual(c.status, "modified")

    def test_status_modified_after_templates_changed(self):
        c = self._create_config(organization=self._get_org(), status="applied")
        self.assertEqual(c.status, "applied")
        t = Template.objects.first()
        c.templates.add(t)
        c.refresh_from_db()
        self.assertEqual(c.status, "modified")
        c.status = "applied"
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.status, "applied")
        c.templates.remove(t)
        c.refresh_from_db()
        self.assertEqual(c.status, "modified")

    def test_status_modified_after_context_changed(self):
        config = self._create_config(
            organization=self._get_org(),
            status="applied",
            config={"interfaces": [{"name": "eth0", "type": "{{ interface_type }}"}]},
            context={"interface_type": "ethernet"},
        )
        config.refresh_from_db()
        self.assertEqual(config.status, "applied")

        with self.subTest("Test changing unused configuration variable"):
            config.context.update({"interface_name": "eth1"})
            config.full_clean()
            config.save()
            config.refresh_from_db()
            self.assertEqual(config.status, "applied")

        with self.subTest("Test changing used configuration variable"):
            config.context = {"interface_type": "virtual"}
            config.full_clean()
            config.save()
            config.refresh_from_db()
            self.assertEqual(config.status, "modified")

    def test_auto_hostname(self):
        c = self._create_config(device=self._create_device(name="automate-me"))
        expected = {"general": {"hostname": "automate-me"}}
        self.assertDictEqual(c.backend_instance.config, expected)
        c.refresh_from_db()
        self.assertDictEqual(c.config, {"general": {}})

        with self.subTest("missing name shall not raise exception"):
            c.device.name = None
            del c.backend_instance
            self.assertDictEqual(c.backend_instance.config, {"general": {}})

    def test_config_context(self):
        config = {
            "general": {
                "id": "{{ id }}",
                "key": "{{ key }}",
                "name": "{{ name }}",
                "mac_address": "{{ mac_address }}",
            }
        }
        c = Config(
            device=self._create_device(name="context-test"),
            backend="netjsonconfig.OpenWrt",
            config=config,
        )
        output = c.backend_instance.render()
        self.assertIn(str(c.device.id), output)
        self.assertIn(c.device.key, output)
        self.assertIn(c.device.name, output)
        self.assertIn(c.device.mac_address, output)

    def test_context_validation(self):
        config = Config(
            device=self._create_device(name="context-test"),
            backend="netjsonconfig.OpenWrt",
            config={},
        )

        for value in [None, "", False]:
            with self.subTest(f"testing {value} in config.context"):
                config.context = value
                config.full_clean()
                self.assertEqual(config.context, {})

        for value in [["a", "b"], '"test"']:
            with self.subTest(
                f"testing {value} in config.context, expecting validation error"
            ):
                config.context = value
                with self.assertRaises(ValidationError) as context_manager:
                    config.full_clean()
                message_dict = context_manager.exception.message_dict
                self.assertIn("context", message_dict)
                self.assertIn(
                    "the supplied value is not a JSON object", message_dict["context"]
                )

    @patch.dict(app_settings.CONTEXT, {"vpnserver1": "vpn.testdomain.com"})
    def test_context_setting(self):
        config = {"general": {"vpnserver1": "{{ vpnserver1 }}"}}
        c = Config(
            device=self._create_device(), backend="netjsonconfig.OpenWrt", config=config
        )
        output = c.backend_instance.render()
        vpnserver1 = app_settings.CONTEXT["vpnserver1"]
        self.assertIn(vpnserver1, output)

    def test_mac_address_as_hostname(self):
        c = self._create_config(device=self._create_device(name="00:11:22:33:44:55"))
        self.assertIn("00-11-22-33-44-55", c.backend_instance.render())

    def test_create_vpnclient(self):
        vpn = self._create_vpn()
        t = self._create_template(name="test-network", type="vpn", vpn=vpn)
        c = self._create_config(device=self._create_device(name="test-create-cert"))
        c.templates.add(t)
        c.save()
        vpnclient = c.vpnclient_set.first()
        self.assertIsNotNone(vpnclient)
        self.assertEqual(c.vpnclient_set.count(), 1)
        self.assertEqual(vpnclient.config, c)
        self.assertEqual(vpnclient.vpn, vpn)

    def test_delete_vpnclient(self):
        self.test_create_vpnclient()
        c = Config.objects.get(device__name="test-create-cert")
        t = Template.objects.get(name="test-network")
        c.templates.remove(t)
        c.save()
        vpnclient = c.vpnclient_set.first()
        self.assertIsNone(vpnclient)
        self.assertEqual(c.vpnclient_set.count(), 0)

    def test_clear_vpnclient(self):
        self.test_create_vpnclient()
        c = Config.objects.get(device__name="test-create-cert")
        c.templates.clear()
        c.save()
        vpnclient = c.vpnclient_set.first()
        self.assertIsNotNone(vpnclient)
        self.assertNotEqual(c.vpnclient_set.count(), 0)

    def test_deleting_template_deletes_vpnclient(self):
        template = self._create_template(
            name="test-network", type="vpn", vpn=self._create_vpn(), default=True
        )
        config = self._create_config(device=self._create_device())
        self.assertEqual(config.vpnclient_set.count(), 1)
        template.delete()
        self.assertEqual(config.templates.count(), 0)
        self.assertEqual(config.vpnclient_set.count(), 0)

    def test_multiple_vpn_clients(self):
        vpn1 = self._create_vpn(name="vpn1")
        vpn2 = self._create_vpn(name="vpn2")
        template1 = self._create_template(name="vpn1-template", type="vpn", vpn=vpn1)
        template2 = self._create_template(name="vpn2-template", type="vpn", vpn=vpn2)
        config = self._create_config(device=self._create_device())

        config.templates.add(template1)
        self.assertEqual(config.vpnclient_set.count(), 1)
        config.templates.set((template1, template2))
        self.assertEqual(config.vpnclient_set.count(), 2)

    def test_create_cert(self):
        vpn = self._create_vpn()
        t = self._create_template(
            name="test-create-cert", type="vpn", vpn=vpn, auto_cert=True
        )
        c = self._create_config(device=self._create_device(name="test-create-cert"))
        c.templates.add(t)
        vpnclient = c.vpnclient_set.first()
        self.assertIsNotNone(vpnclient)
        self.assertTrue(vpnclient.auto_cert)
        self.assertIsNotNone(vpnclient.cert)
        self.assertEqual(c.vpnclient_set.count(), 1)

    def test_automatically_created_cert_common_name_format(self):
        self.test_create_cert()
        c = Config.objects.get(device__name="test-create-cert")
        vpnclient = c.vpnclient_set.first()
        expected_cn = app_settings.COMMON_NAME_FORMAT.format(**c.device.__dict__)
        self.assertIn(expected_cn, vpnclient.cert.common_name)

    def test_automatically_created_cert_not_deleted_post_clear(self):
        self.test_create_cert()
        c = Config.objects.get(device__name="test-create-cert")
        vpnclient = c.vpnclient_set.first()
        cert = vpnclient.cert
        cert_model = cert.__class__
        c.templates.clear()
        self.assertNotEqual(c.vpnclient_set.count(), 0)
        self.assertNotEqual(cert_model.objects.filter(pk=cert.pk).count(), 0)

    def test_automatically_created_cert_revoked_post_remove(self):
        self.test_create_cert()
        c = Config.objects.get(device__name="test-create-cert")
        t = Template.objects.get(name="test-create-cert")
        vpnclient = c.vpnclient_set.first()
        cert = vpnclient.cert
        cert_model = cert.__class__
        c.templates.remove(t)
        self.assertEqual(c.vpnclient_set.count(), 0)
        self.assertEqual(cert_model.objects.filter(pk=cert.pk, revoked=True).count(), 1)

    def test_create_cert_false(self):
        vpn = self._create_vpn()
        t = self._create_template(type="vpn", auto_cert=False, vpn=vpn)
        c = self._create_config(device=self._create_device(name="test-create-cert"))
        c.templates.add(t)
        c.save()
        vpnclient = c.vpnclient_set.first()
        self.assertIsNotNone(vpnclient)
        self.assertFalse(vpnclient.auto_cert)
        self.assertIsNone(vpnclient.cert)
        self.assertEqual(c.vpnclient_set.count(), 1)

    def test_cert_not_deleted_on_config_change(self):
        vpn = self._create_vpn()
        t = self._create_template(type="vpn", auto_cert=True, vpn=vpn)
        c = self._create_config(device=self._create_device(name="test-device"))
        c.templates.add(t)
        c.save()
        vpnclient = c.vpnclient_set.first()
        cert = vpnclient.cert
        cert_model = cert.__class__

        with self.subTest(
            "Ensure that the VpnClient and x509 Cert instance is created"
        ):
            self.assertIsNotNone(vpnclient)
            self.assertTrue(vpnclient.auto_cert)
            self.assertIsNotNone(vpnclient.cert)

        c.templates.clear()
        with self.subTest("Ensure that VpnClient and Cert instance are not deleted"):
            self.assertIsNotNone(c.vpnclient_set.first())
            self.assertNotEqual(c.vpnclient_set.count(), 0)
            self.assertNotEqual(cert_model.objects.filter(pk=cert.pk).count(), 0)

        # add the template again
        c.templates.add(t)
        c.save()
        with self.subTest("Ensure no additional VpnClients are created"):
            self.assertEqual(c.vpnclient_set.count(), 1)
            self.assertEqual(c.vpnclient_set.first(), vpnclient)

    def test_auto_cert_not_deleted_on_device_deactivation(self):
        self._create_template(type="vpn", vpn=self._create_vpn(), default=True)
        config = self._create_config(organization=self._get_org())
        self.assertEqual(config.templates.count(), 1)
        cert = config.vpnclient_set.first().cert
        self.assertEqual(cert.revoked, False)

        config.deactivate()
        config.refresh_from_db()
        # Since it is possible to refresh the cert object from the
        # database, it means that the cert object is not deleted.
        cert.refresh_from_db()
        self.assertEqual(config.status, "deactivating")
        self.assertEqual(config.templates.count(), 0)
        self.assertEqual(cert.revoked, True)

    def test_certificate_updated_skipped_for_deactivated_config(self):
        self._create_template(type="vpn", vpn=self._create_vpn(), default=True)
        config = self._create_config(organization=self._get_org())
        cert = config.vpnclient_set.first().cert
        config.deactivate()
        config.refresh_from_db()
        self.assertEqual(config.status, "deactivating")
        # VpnClient is deleted on deactivation; cert is auto-revoked.
        self.assertEqual(config.vpnclient_set.count(), 0)
        # Un-revoke the cert so _resolve_cert_dependency() bypasses the early
        # "if revoked: return" guard and hits the ObjectDoesNotExist path.
        # The Cert CacheDependency defers to transaction.on_commit, which
        # TestCase does not fire unless captured.
        cert.revoked = False
        with self.captureOnCommitCallbacks(execute=True):
            cert.save()
        # Config status must not change: _resolve_cert_dependency() returns
        # early because the VpnClient was deleted during deactivation.
        config.refresh_from_db()
        self.assertEqual(config.status, "deactivating")

    def _get_vpn_context(self):
        self.test_create_cert()
        c = Config.objects.get(device__name="test-create-cert")
        context = c.get_context()
        vpnclient = c.vpnclient_set.first()
        return context, vpnclient

    def test_vpn_context_ca_path(self):
        context, vpnclient = self._get_vpn_context()
        ca = vpnclient.cert.ca
        key = "ca_path_{0}".format(vpnclient.vpn.pk.hex)
        filename = "ca-{0}-{1}.pem".format(ca.pk, ca.common_name)
        value = "{0}/{1}".format(app_settings.CERT_PATH, filename)
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_ca_path_bug(self):
        vpn = self._create_vpn(ca_options={"common_name": "common name CA"})
        t = self._create_template(type="vpn", auto_cert=True, vpn=vpn)
        c = self._create_config(device=self._create_device(name="test-create-cert"))
        c.templates.add(t)
        context = c.get_context()
        ca = vpn.ca
        key = "ca_path_{0}".format(vpn.pk.hex)
        filename = "ca-{0}-{1}.pem".format(ca.pk, ca.common_name.replace(" ", "_"))
        value = "{0}/{1}".format(app_settings.CERT_PATH, filename)
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_ca_contents(self):
        context, vpnclient = self._get_vpn_context()
        key = "ca_contents_{0}".format(vpnclient.vpn.pk.hex)
        value = vpnclient.cert.ca.certificate
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_cert_path(self):
        context, vpnclient = self._get_vpn_context()
        vpn_pk = vpnclient.vpn.pk.hex
        key = "cert_path_{0}".format(vpn_pk)
        filename = "client-{0}.pem".format(vpn_pk)
        value = "{0}/{1}".format(app_settings.CERT_PATH, filename)
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_cert_contents(self):
        context, vpnclient = self._get_vpn_context()
        vpn_pk = vpnclient.vpn.pk.hex
        key = "cert_contents_{0}".format(vpn_pk)
        value = vpnclient.cert.certificate
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_key_path(self):
        context, vpnclient = self._get_vpn_context()
        vpn_pk = vpnclient.vpn.pk.hex
        key = "key_path_{0}".format(vpn_pk)
        filename = "key-{0}.pem".format(vpn_pk)
        value = "{0}/{1}".format(app_settings.CERT_PATH, filename)
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_key_contents(self):
        context, vpnclient = self._get_vpn_context()
        vpn_pk = vpnclient.vpn.pk.hex
        key = "key_contents_{0}".format(vpn_pk)
        value = vpnclient.cert.private_key
        self.assertIn(key, context)
        self.assertIn(value, context[key])

    def test_vpn_context_no_cert(self):
        vpn = self._create_vpn()
        t = self._create_template(type="vpn", auto_cert=False, vpn=vpn)
        c = self._create_config(device=self._create_device(name="test-create-cert"))
        c.templates.add(t)
        c.save()
        context = c.get_context()
        vpn_id = vpn.pk.hex
        cert_path_key = "cert_path_{0}".format(vpn_id)
        cert_contents_key = "cert_contents_{0}".format(vpn_id)
        key_path_key = "key_path_{0}".format(vpn_id)
        key_contents_key = "key_contents_{0}".format(vpn_id)
        ca_path_key = "ca_path_{0}".format(vpn_id)
        ca_contents_key = "ca_contents_{0}".format(vpn_id)
        self.assertNotIn(cert_path_key, context)
        self.assertNotIn(cert_contents_key, context)
        self.assertNotIn(key_path_key, context)
        self.assertNotIn(key_contents_key, context)
        self.assertIn(ca_path_key, context)
        self.assertIn(ca_contents_key, context)

    def test_m2m_str_conversion(self):
        t = self._create_template()
        c = self._create_config(device=self._create_device(name="test-m2m-str-repr"))
        c.templates.add(t)
        c.save()
        through = str(c.templates.through.objects.first())
        self.assertIn("Relationship with", through)
        self.assertIn(t.name, through)

    def test_get_template_model_static(self):
        self.assertIs(Config.get_template_model(), Template)

    def test_get_template_model_bound(self):
        self.assertIs(Config().get_template_model(), Template)

    def test_remove_duplicate_files(self):
        template1 = self._create_template(
            name="test-vpn-1",
            config={
                "files": [
                    {
                        "path": "/etc/vpnserver1",
                        "mode": "0644",
                        "contents": "{{ name }}\n{{ vpnserver1 }}\n",
                    }
                ]
            },
        )
        template2 = self._create_template(
            name="test-vpn-2",
            config={
                "files": [
                    {
                        "path": "/etc/vpnserver1",
                        "mode": "0644",
                        "contents": "{{ name }}\n{{ vpnserver1 }}\n",
                    }
                ]
            },
        )
        org = self._get_org()
        with self.subTest("Test template applied on creating config"):
            try:
                config = self._create_config(
                    organization=org,
                    templates=[template1, template2],
                )
                result = config.get_backend_instance(
                    template_instances=[template1, template2]
                ).render()
            except ValidationError:
                self.fail("ValidationError raised!")
            else:
                self.assertIn("# path: /etc/vpnserver1", result)

        config.device.delete(check_deactivated=False)
        config.delete()
        with self.subTest("Test template applied after creating config object"):
            config = self._create_config(organization=org)
            config.templates.add(template1)
            config.templates.add(template2)
            config.refresh_from_db()
            try:
                result = config.get_backend_instance(
                    template_instances=[template1, template2]
                ).render()
            except ValidationError:
                self.fail("ValidationError raised!")
            else:
                self.assertIn("# path: /etc/vpnserver1", result)

    def test_duplicated_files_in_config(self):
        try:
            self._create_config(
                organization=self._get_org(),
                config={
                    "files": [
                        {
                            "path": "/etc/vpnserver1",
                            "mode": "0644",
                            "contents": "{{ name }}\n{{ vpnserver1 }}\n",
                        },
                        {
                            "path": "/etc/vpnserver1",
                            "mode": "0644",
                            "contents": "{{ name }}\n{{ vpnserver1 }}\n",
                        },
                    ]
                },
            )
        except ValidationError as e:
            self.assertIn('Invalid configuration triggered by "#/files"', str(e))
        else:
            self.fail("ValidationError not raised!")

    def test_config_with_shared_template(self):
        org = self._get_org()
        config = self._create_config(organization=org)
        # shared template
        template = self._create_template()
        # add shared template
        config.templates.add(template)
        self.assertIsNone(template.organization)
        self.assertEqual(config.templates.first().pk, template.pk)

    def test_config_and_template_different_organization(self):
        org1 = self._get_org()
        org2 = self._create_org(name="test org2", slug="test-org2")
        template = self._create_template(organization=org1)
        config = self._create_config(organization=org2)
        try:
            config.templates.add(template)
        except ValidationError as e:
            self.assertIn("do not match the organization", e.messages[0])
        else:
            self.fail("ValidationError not raised")

    def test_config_status_changed_not_sent_on_creation(self):
        org = self._get_org()
        with catch_signal(config_status_changed) as handler:
            self._create_config(organization=org)
            handler.assert_not_called()

    def test_config_status_changed_modified(self):
        org = self._get_org()
        with catch_signal(config_status_changed) as handler:
            c = self._create_config(organization=org, status="applied")
            handler.assert_not_called()
            self.assertEqual(c.status, "applied")

        with catch_signal(config_status_changed) as handler:
            c.config = {"general": {"description": "test"}}
            c.full_clean()
            c.save()
            handler.assert_called_once_with(
                sender=Config, signal=config_status_changed, instance=c
            )
            self.assertEqual(c.status, "modified")

        with catch_signal(config_status_changed) as handler:
            c.config = {"general": {"description": "changed again"}}
            c.full_clean()
            c.save()
            handler.assert_not_called()
            self.assertEqual(c.status, "modified")

    def test_config_modified_sent(self):
        org = self._get_org()
        with catch_signal(config_modified) as handler:
            c = self._create_config(organization=org, status="applied")
            handler.assert_not_called()
            self.assertEqual(c.status, "applied")

        with catch_signal(config_modified) as handler:
            c.config = {"general": {"description": "test"}}
            c.full_clean()
            c.save()
            handler.assert_called_once_with(
                sender=Config,
                signal=config_modified,
                instance=c,
                device=c.device,
                config=c,
                previous_status="applied",
                action="config_changed",
            )
            self.assertEqual(c.status, "modified")

        with catch_signal(config_modified) as handler:
            c.config = {"general": {"description": "changed again"}}
            c.full_clean()
            # repeated on purpose
            c.full_clean()
            c.save()
            handler.assert_called_once_with(
                sender=Config,
                signal=config_modified,
                instance=c,
                device=c.device,
                config=c,
                previous_status="modified",
                action="config_changed",
            )
            self.assertEqual(c.status, "modified")

    def test_check_changes_query(self):
        config = self._create_config(organization=self._get_org())
        with self.subTest("No changes made to the config object"):
            with self.assertNumQueries(3):
                config._check_changes()

        with self.subTest("Changes made to the config object"):
            config.templates.add(self._create_template())
            config.config = {"general": {"description": "test"}}
            with self.assertNumQueries(4):
                config._check_changes()

    def test_config_get_system_context(self):
        config = self._create_config(
            organization=self._get_org(), context={"test": "value"}
        )
        system_context = config.get_system_context()
        self.assertNotIn("test", system_context.keys())

    def test_initial_status(self):
        config = self._create_config(
            organization=self._get_org(), context={"test": "value"}
        )
        self.assertEqual(config._initial_status, config.status)
        config.status = "modified"
        config.save()
        self.assertEqual(config._initial_status, "modified")

    def test_config_backend_changed(self):
        org = self._get_org()
        old_backend = "netjsonconfig.OpenWrt"
        backend = "netjsonconfig.OpenWisp"
        group = self._create_device_group(organization=org)
        t1 = self._create_template(name="t1", backend=old_backend)
        t2 = self._create_template(name="t2", backend=backend)
        group.templates.add(*[t1, t2])
        with self.subTest("config_backend_changed signal must not be sent on creation"):
            with catch_signal(config_backend_changed) as handler:
                d = self._create_device(group=group, organization=org)
                handler.assert_not_called()
                self.assertTrue(d.config.templates.filter(pk=t1.pk).exists())
                self.assertFalse(d.config.templates.filter(pk=t2.pk).exists())
        with self.subTest(
            "config_backend_changed signal must not be sent on config status change"
        ):
            with catch_signal(config_backend_changed) as handler:
                c = d.config
                c.status = "applied"
                c.save(update_fields=["status"])
                handler.assert_not_called()
        with self.subTest(
            "config_backend_changed signal must be sent on backend change"
        ):
            with catch_signal(config_backend_changed) as handler:
                c = d.config
                c.backend = backend
                c.save(update_fields=["backend"])
                handler.assert_called_once_with(
                    sender=Config,
                    signal=config_backend_changed,
                    instance=c,
                    old_backend=old_backend,
                    backend=backend,
                )
                self.assertTrue(d.config.templates.filter(pk=t2.pk).exists())
                self.assertFalse(d.config.templates.filter(pk=t1.pk).exists())

    def test_devicegroup_context_change_defers_checksum_invalidation_to_commit(self):
        """
        Regression test for the DeviceGroup CacheDependency (deferred to
        commit, default on_commit=True): the Celery task recomputing the
        group's configs must be enqueued only after the transaction that
        changed the group's context has committed, otherwise a worker
        picking up the task can read the DB before the commit and wrongly
        conclude the context did not change.
        """
        device_group = self._create_device_group(context={"interface_type": "eth0"})
        with patch(
            "openwisp_controller.config.tasks"
            ".bulk_invalidate_config_get_cached_checksum.delay"
        ) as mocked_delay:
            with self.captureOnCommitCallbacks(execute=True):
                device_group.context = {"interface_type": "eth1"}
                device_group.full_clean()
                device_group.save()
                mocked_delay.assert_not_called()
            mocked_delay.assert_called_once_with(
                {"device__group_id": str(device_group.id)}
            )

    def test_organization_context_change_defers_checksum_invalidation_to_commit(self):
        """
        Same as the DeviceGroup regression test above, but for the
        OrganizationConfigSettings CacheDependency.
        """
        org_settings = OrganizationConfigSettings.objects.create(
            organization=self._get_org(), context={"interface_type": "eth0"}
        )
        with patch(
            "openwisp_controller.config.tasks"
            ".bulk_invalidate_config_get_cached_checksum.delay"
        ) as mocked_delay:
            with self.captureOnCommitCallbacks(execute=True):
                org_settings.context = {"interface_type": "eth1"}
                org_settings.full_clean()
                org_settings.save()
                mocked_delay.assert_not_called()
            mocked_delay.assert_called_once_with(
                {"device__organization_id": str(org_settings.organization_id)}
            )

    def test_devicegroup_delete_invalidates_cache_deferred_to_commit(self):
        """
        Regression test for the DeviceGroup post_delete CacheDependency
        (config/apps.py), which targets ``devicegroup_delete_handler``: the
        Celery task invalidating the DeviceGroupCommonName cache must be
        enqueued only after the deleting transaction has committed,
        otherwise a concurrent request can repopulate the cache from a
        device group that is about to be deleted, leaving it stale after
        commit.
        """
        org = self._get_org()
        device_group = self._create_device_group(organization=org)
        device_group_id = device_group.id
        with patch(
            "openwisp_controller.config.tasks"
            ".invalidate_devicegroup_cache_delete.delay"
        ) as mocked_delay:
            with self.captureOnCommitCallbacks(execute=True):
                device_group.delete()
                mocked_delay.assert_not_called()
            mocked_delay.assert_called_once_with(
                device_group_id,
                DeviceGroup._meta.model_name,
                organization_id=org.id,
            )

    def test_cert_delete_invalidates_devicegroup_cache_deferred_to_commit(self):
        """
        Same as above, but for the Cert post_delete CacheDependency, which
        also targets ``devicegroup_delete_handler``.
        """
        org = self._get_org()
        cert = self._create_cert(organization=org)
        cert_id = cert.id
        common_name = cert.common_name
        with patch(
            "openwisp_controller.config.tasks"
            ".invalidate_devicegroup_cache_delete.delay"
        ) as mocked_delay:
            with self.captureOnCommitCallbacks(execute=True):
                cert.delete()
                mocked_delay.assert_not_called()
            mocked_delay.assert_called_once_with(
                cert_id,
                Cert._meta.model_name,
                common_name=common_name,
                organization_slug=org.slug,
            )

    def test_shared_cert_delete_invalidates_devicegroup_wildcard_cache(self):
        """
        A Cert with organization=None ("shared" cert, usable across
        multiple organizations) is still reachable via the no-org (``""``)
        DeviceGroupCommonName cache key: ``get_device_group`` only filters
        by organization when one is explicitly requested. Deleting the cert
        must still invalidate that wildcard entry, even though there is no
        organization_slug to also invalidate an org-scoped entry.
        """
        cert = self._create_cert(organization=None)
        cert_id = cert.id
        common_name = cert.common_name
        with patch(
            "openwisp_controller.config.tasks"
            ".invalidate_devicegroup_cache_delete.delay"
        ) as mocked_delay:
            with self.captureOnCommitCallbacks(execute=True):
                cert.delete()
                mocked_delay.assert_not_called()
            mocked_delay.assert_called_once_with(
                cert_id,
                Cert._meta.model_name,
                common_name=common_name,
            )

    def test_shared_cert_delete_task_invalidates_devicegroup_wildcard_cache(self):
        cert = self._create_cert(organization=None)
        common_name = cert.common_name
        with patch(
            "openwisp_controller.config.api.views.DeviceGroupCommonName"
            ".certificate_delete_invalidates_cache"
        ) as mocked_invalidate:
            tasks.invalidate_devicegroup_cache_delete(
                cert.id,
                Cert._meta.model_name,
                common_name=common_name,
            )
        mocked_invalidate.assert_called_once_with(common_name, None)


class TestTransactionConfig(
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    TestWireguardVpnMixin,
    TransactionTestCase,
):
    def test_multiple_vpn_client_templates_same_vpn(self):
        vpn1 = self._create_vpn(name="vpn1")
        vpn2 = self._create_vpn(name="vpn2")
        vpn1_template1 = self._create_template(
            name="vpn1-template1", type="vpn", vpn=vpn1
        )
        vpn1_template2 = self._create_template(
            name="vpn1-template2", type="vpn", vpn=vpn1
        )
        vpn2_template1 = self._create_template(
            name="vpn2-template1", type="vpn", vpn=vpn2
        )
        vpn2_template2 = self._create_template(
            name="vpn2-template2", type="vpn", vpn=vpn2
        )
        vpn2_template3 = self._create_template(
            name="vpn2-template3", type="vpn", vpn=vpn2
        )
        config = self._create_config(device=self._create_device())
        config.templates.add(vpn1_template1)
        with self.subTest("Adding duplicate vpn-client template one at time"):
            with self.assertRaises(ValidationError) as context_manager:
                config.templates.add(vpn1_template2)
            try:
                self.assertEqual(
                    context_manager.exception.message,
                    "You cannot select multiple VPN client templates related to the"
                    " same VPN server.\n"
                    'The templates "vpn1-template1" and "vpn1-template2" are all'
                    ' linked to the same VPN server: "vpn1".',
                )
            except AssertionError:
                self.fail("ValidationError not raised")

        with self.subTest("Add multiple vpn client templates for multiple VPN"):
            config.refresh_from_db()
            self.assertEqual(config.templates.count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 1)
            with self.assertRaises(ValidationError) as context_manager:
                config.templates.add(
                    vpn1_template2, vpn2_template1, vpn2_template2, vpn2_template3
                )
            try:
                self.assertEqual(
                    context_manager.exception.message,
                    "You cannot select multiple VPN client templates related to the"
                    " same VPN server.\n"
                    'The templates "vpn1-template1" and "vpn1-template2" are all'
                    ' linked to the same VPN server: "vpn1".\n'
                    'The templates "vpn2-template1", "vpn2-template2" and'
                    ' "vpn2-template3" are all linked to the same VPN server: "vpn2".',
                )
            except AssertionError:
                self.fail("ValidationError not raised")

    def test_certificate_renew_invalidates_checksum_cache(self):
        config = self._create_config(organization=self._get_org())
        vpn_template = self._create_template(
            name="vpn1-template", type="vpn", vpn=self._create_vpn(), config={}
        )
        config.templates.add(vpn_template)
        config.refresh_from_db()
        with patch("django.core.cache.cache.delete") as mocked_delete:
            # Comparing checksum values after deleting backend instance
            # makes the test bogus. Hence assertion for cache.delete is required
            old_checksum = config.checksum
            vpnclient_cert = config.vpnclient_set.first().cert
            vpnclient_cert.renew()
            # An additional call from cache invalidation of
            # DeviceGroupCommonName View
            self.assertEqual(mocked_delete.call_count, 3)
            del config.backend_instance
            self.assertNotEqual(config.get_cached_checksum(), old_checksum)
            config.refresh_from_db()
            self.assertEqual(config.status, "modified")

    def test_device_os_change_updates_config_checksum(self):
        org = self._get_org()
        device = self._create_device(
            name="test", organization=org, os="OpenWrt 19.07.0"
        )
        config = self._create_config(
            device=device,
            backend="netjsonconfig.OpenWrt",
            config={
                "interfaces": [
                    {
                        "name": "eth0",
                        "type": "ethernet",
                        "addresses": [{"proto": "dhcp", "family": "ipv4"}],
                    }
                ]
            },
        )
        config.set_status_applied()
        config.refresh_from_db()
        old_checksum_db = config.checksum_db
        self.assertEqual(config.status, "applied")
        # changing the OS toggles DSA (disabled on 19.x, enabled on 21.x),
        # which changes the rendered configuration
        device.os = "OpenWrt 21.02.0"
        device.save()
        config = Config.objects.get(pk=config.pk)
        self.assertEqual(config.status, "modified")
        self.assertNotEqual(config.checksum_db, old_checksum_db)
        self.assertEqual(config.checksum_db, config.checksum)

    def test_device_org_change_updates_config_checksum(self):
        org1 = self._get_org()
        OrganizationConfigSettings.objects.create(
            organization=org1, context={"interface_type": "ethernet"}
        )
        org2 = self._create_org(name="org2", slug="org2")
        OrganizationConfigSettings.objects.create(
            organization=org2, context={"interface_type": "virtual"}
        )
        device = self._create_device(name="test", organization=org1)
        template = self._create_template(
            config={"interfaces": [{"name": "eth0", "type": "{{ interface_type }}"}]},
            default_values={"interface_type": "ethernet"},
        )
        config = self._create_config(device=device)
        config.templates.add(template)
        config.set_status_applied()
        config.refresh_from_db()
        old_checksum_db = config.checksum_db
        self.assertEqual(config.status, "applied")
        # changing the organization changes the org-level context,
        # which changes the rendered configuration
        device.organization = org2
        device.save()
        config = Config.objects.get(pk=config.pk)
        self.assertEqual(config.status, "modified")
        self.assertNotEqual(config.checksum_db, old_checksum_db)
        self.assertEqual(config.checksum_db, config.checksum)

    def test_device_group_change_updates_config_checksum(self):
        org = self._get_org()
        group1 = DeviceGroup(
            name="group1", organization=org, context={"interface_type": "ethernet"}
        )
        group1.full_clean()
        group1.save()
        group2 = DeviceGroup(
            name="group2", organization=org, context={"interface_type": "virtual"}
        )
        group2.full_clean()
        group2.save()
        device = self._create_device(name="test", organization=org, group=group1)
        template = self._create_template(
            config={"interfaces": [{"name": "eth0", "type": "{{ interface_type }}"}]},
            default_values={"interface_type": "ethernet"},
        )
        config = self._create_config(device=device)
        config.templates.add(template)
        config.set_status_applied()
        config.refresh_from_db()
        old_checksum_db = config.checksum_db
        self.assertEqual(config.status, "applied")
        device.group = group2
        device.save()
        config = Config.objects.get(pk=config.pk)
        self.assertEqual(config.status, "modified")
        self.assertNotEqual(config.checksum_db, old_checksum_db)
        self.assertEqual(config.checksum_db, config.checksum)

    def test_checksum_db_accounts_for_vpnclient(self):
        vpn = self._create_wireguard_vpn()
        vpn_template = self._create_template(
            name="vpn1-template", type="vpn", vpn=vpn, config={}
        )
        config = self._create_config(organization=self._get_org())
        config.templates.add(vpn_template)
        config.refresh_from_db()
        config._invalidate_backend_instance_cache()
        self.assertEqual(config.checksum, config.checksum_db)

    def test_deleting_template_invalidates_config_checksum(self):
        template = self._create_template(
            name="test-template",
            config={"interfaces": [{"name": "eth0", "type": "ethernet"}]},
        )
        config = self._create_config(device=self._create_device())
        config.templates.add(template)
        config.set_status_applied()
        config.refresh_from_db()
        old_checksum_db = config.checksum_db
        self.assertEqual(config.status, "applied")
        template.delete()
        config = Config.objects.get(pk=config.pk)
        self.assertNotEqual(config.checksum_db, old_checksum_db)
        self.assertEqual(config.checksum_db, config.checksum)
        self.assertEqual(config.status, "modified")

    def test_bulk_deleting_templates_invalidates_config_checksum(self):
        template1 = self._create_template(
            name="test-template1",
            config={"interfaces": [{"name": "eth0", "type": "ethernet"}]},
        )
        template2 = self._create_template(
            name="test-template2",
            config={"interfaces": [{"name": "eth1", "type": "ethernet"}]},
        )
        config1 = self._create_config(device=self._create_device(name="device1"))
        config1.templates.add(template1)
        config2 = self._create_config(
            device=self._create_device(name="device2", mac_address="00:11:22:33:44:66")
        )
        config2.templates.add(template2)
        for config in (config1, config2):
            config.set_status_applied()
        config1.refresh_from_db()
        config2.refresh_from_db()
        old_checksum_db1 = config1.checksum_db
        old_checksum_db2 = config2.checksum_db
        self.assertEqual(config1.status, "applied")
        self.assertEqual(config2.status, "applied")
        # bulk delete via a queryset, not per-instance .delete() calls
        Template.objects.filter(pk__in=[template1.pk, template2.pk]).delete()
        config1 = Config.objects.get(pk=config1.pk)
        config2 = Config.objects.get(pk=config2.pk)
        self.assertNotEqual(config1.checksum_db, old_checksum_db1)
        self.assertEqual(config1.checksum_db, config1.checksum)
        self.assertEqual(config1.status, "modified")
        self.assertNotEqual(config2.checksum_db, old_checksum_db2)
        self.assertEqual(config2.checksum_db, config2.checksum)
        self.assertEqual(config2.status, "modified")

    def test_deleting_vpn_invalidates_config_checksum(self):
        device, vpn, _ = self._create_wireguard_vpn_template()
        config = device.config
        config.set_status_applied()
        config.refresh_from_db()
        old_checksum_db = config.checksum_db
        self.assertEqual(config.status, "applied")
        # deleting the VPN cascades to delete its VPN-type template
        # (Template.vpn is on_delete=CASCADE); the config using that
        # template is not deleted (Config.templates is a many-to-many
        # field), so its checksum must still be recomputed.
        vpn.delete()
        self.assertEqual(Template.objects.count(), 0)
        config = Config.objects.get(pk=config.pk)
        self.assertNotEqual(config.checksum_db, old_checksum_db)
        self.assertEqual(config.checksum_db, config.checksum)
        self.assertEqual(config.status, "modified")


class TestCacheDependency(CreateConfigTemplateMixin, CreateDeviceGroupMixin, TestCase):
    """
    Unit tests for the declarative cache-invalidation engine
    (``CacheDependency``) that centralizes cache/checksum invalidation
    (issue #1095).
    """

    def _connect(self, **kwargs):
        dependency = CacheDependency(**kwargs)
        dependency.connect(dispatch_uid="test.cache_dependency")
        self.addCleanup(dependency.disconnect)
        return dependency

    def test_target_invoked_on_related_change(self):
        target = Mock()
        self._connect(
            source="config.DeviceGroup",
            signal="post_save",
            on_commit=False,
            resolve=lambda instance, **kwargs: [instance],
            target=target,
        )
        # creation is skipped by default (on_create=False)
        group = self._create_device_group()
        target.assert_not_called()
        # an update fires the dependency with the resolved object
        group.name = "renamed"
        group.save()
        target.assert_called_once_with(group)

    def test_on_create_opt_in(self):
        target = Mock()
        self._connect(
            source="config.DeviceGroup",
            signal="post_save",
            on_create=True,
            on_commit=False,
            resolve=lambda instance, **kwargs: [instance],
            target=target,
        )
        group = self._create_device_group()
        target.assert_called_once_with(group)

    def test_track_fields_fires_only_on_value_change(self):
        target = Mock()
        self._connect(
            source="config.DeviceGroup",
            signal="post_save",
            track_fields=["context"],
            on_commit=False,
            resolve=lambda instance, **kwargs: [instance],
            target=target,
        )
        group = self._create_device_group(context={"a": "1"})
        target.assert_not_called()
        with self.subTest("save without changing tracked field"):
            group.name = "renamed"
            group.save()
            target.assert_not_called()
        with self.subTest("save changing tracked field"):
            group.context = {"a": "2"}
            group.save()
            target.assert_called_once_with(group)

    def test_snapshot_not_reused_across_saves(self):
        """
        A snapshot from a prior save must be consumed so a later
        save(update_fields=...) that excludes the tracked field cannot compare
        against the stale snapshot and fire the target a second time.
        """
        target = Mock()
        self._connect(
            source="config.DeviceGroup",
            signal="post_save",
            track_fields=["context"],
            on_commit=False,
            resolve=lambda instance, **kwargs: [instance],
            target=target,
        )
        group = self._create_device_group(context={"a": "1"})
        group.context = {"a": "2"}
        group.save()
        target.assert_called_once_with(group)
        # a subsequent save that does not touch the tracked field must not
        # re-fire the target because of a leftover snapshot
        target.reset_mock()
        group.name = "renamed"
        group.save(update_fields=["name"])
        target.assert_not_called()

    def test_target_as_method_name(self):
        # a string target is invoked as a method on each resolved object
        dependency = CacheDependency(
            source="config.DeviceGroup",
            signal="post_save",
            resolve=lambda instance, **kwargs: [instance],
            target="some_method",
        )
        obj = Mock()
        dependency._apply([obj])
        obj.some_method.assert_called_once_with()

    def test_snapshot_uses_initial_values_when_all_tracked_fields_available(self):
        dependency = CacheDependency(
            source="config.Device",
            signal="post_save",
            track_fields=["name", "organization_id"],
            target=Mock(),
        )
        dependency._uid = "test.cache_dependency.snapshot.initial"
        device = self._create_device(name="device-initial")
        old_name = device._initial_name
        old_org_id = device._initial_organization_id
        # Emulate pre_save state where current values may differ from initial ones.
        device.name = "device-updated"

        with patch.object(
            dependency,
            "_snapshot_from_initial_values",
            wraps=dependency._snapshot_from_initial_values,
        ) as initial_spy, patch.object(
            dependency,
            "_snapshot_from_db",
            wraps=dependency._snapshot_from_db,
        ) as db_spy:
            dependency._snapshot_handler(Device, device)

        initial_spy.assert_called_once_with(device)
        db_spy.assert_not_called()
        snapshot = device._cache_dependency_snapshots[dependency._uid]
        self.assertEqual(snapshot["name"], old_name)
        self.assertEqual(snapshot["organization_id"], old_org_id)

    def test_snapshot_falls_back_to_db_when_initial_fields_are_missing(self):
        dependency = CacheDependency(
            source="config.DeviceGroup",
            signal="post_save",
            track_fields=["context"],
            target=Mock(),
        )
        dependency._uid = "test.cache_dependency.snapshot.db_fallback"
        group = self._create_device_group(context={"a": "1"})

        with patch.object(
            dependency,
            "_snapshot_from_initial_values",
            wraps=dependency._snapshot_from_initial_values,
        ) as initial_spy, patch.object(
            dependency,
            "_snapshot_from_db",
            wraps=dependency._snapshot_from_db,
        ) as db_spy:
            dependency._snapshot_handler(DeviceGroup, group)

        initial_spy.assert_called_once_with(group)
        db_spy.assert_called_once_with(DeviceGroup, group)
        snapshot = group._cache_dependency_snapshots[dependency._uid]
        self.assertEqual(snapshot["context"], {"a": "1"})

    def test_snapshot_falls_back_to_db_when_initial_fields_are_deferred(self):
        dependency = CacheDependency(
            source="config.Device",
            signal="post_save",
            track_fields=["name", "organization_id"],
            target=Mock(),
        )
        dependency._uid = "test.cache_dependency.snapshot.deferred"
        device = self._create_device(name="device-deferred")
        deferred_device = Device.objects.only("id").get(pk=device.pk)
        self.assertEqual(deferred_device._initial_name, models.DEFERRED)
        self.assertEqual(deferred_device._initial_organization_id, models.DEFERRED)

        with patch.object(
            dependency,
            "_snapshot_from_initial_values",
            wraps=dependency._snapshot_from_initial_values,
        ) as initial_spy, patch.object(
            dependency,
            "_snapshot_from_db",
            wraps=dependency._snapshot_from_db,
        ) as db_spy:
            dependency._snapshot_handler(Device, deferred_device)

        initial_spy.assert_called_once_with(deferred_device)
        db_spy.assert_not_called()
        snapshot = deferred_device._cache_dependency_snapshots[dependency._uid]
        self.assertEqual(snapshot["name"], models.DEFERRED)
        self.assertEqual(snapshot["organization_id"], models.DEFERRED)

    def test_snapshot_skips_when_update_fields_excludes_tracked_fields(self):
        dependency = CacheDependency(
            source="config.Device",
            signal="post_save",
            track_fields=["os", "group_id", "organization_id"],
            target=Mock(),
        )
        dependency._uid = "test.cache_dependency.snapshot.skip_irrelevant_update_fields"
        device = self._create_device(os="OpenWrt 22.03")

        with patch.object(
            dependency,
            "_snapshot_from_initial_values",
            wraps=dependency._snapshot_from_initial_values,
        ) as initial_spy, patch.object(
            dependency,
            "_snapshot_from_db",
            wraps=dependency._snapshot_from_db,
        ) as db_spy:
            dependency._snapshot_handler(
                Device, device, update_fields={"management_ip", "last_ip"}
            )

        initial_spy.assert_not_called()
        db_spy.assert_not_called()
        snapshots = getattr(device, dependency._SNAPSHOT_ATTR, {})
        self.assertNotIn(dependency._uid, snapshots)

    def test_registry_tracks_connect_and_disconnect(self):
        uid = "test.cache_dependency.registry"
        dependency = CacheDependency(
            source="config.DeviceGroup", signal="post_save", target=Mock()
        )
        self.assertNotIn(uid, CacheDependency._registry)
        dependency.connect(dispatch_uid=uid)
        self.assertIs(CacheDependency._registry[uid], dependency)
        dependency.disconnect()
        self.assertNotIn(uid, CacheDependency._registry)

    def test_registry_includes_core_dependencies(self):
        # the app-level and model-owned dependencies are wired at app startup
        targets = {
            dep.describe()["target"]
            for dep in CacheDependency.get_registered_dependencies()
        }
        self.assertIn("update_status_if_checksum_changed", targets)
        self.assertIn("DeviceChecksumView.invalidate_get_device_cache", targets)
        self.assertIn("AbstractVpn._invalidate_vpn_view_cache", targets)

    def test_describe_reports_dependency_attributes(self):
        dependency = self._connect(
            source="config.Device",
            signal="post_save",
            track_fields=["os", "group_id", "organization_id"],
            resolve=Config._resolve_device_dependency,
            target="update_status_if_checksum_changed",
        )
        info = dependency.describe()
        self.assertEqual(info["source"], Device._meta.label_lower)
        self.assertEqual(info["signal"], "post_save")
        self.assertEqual(info["target"], "update_status_if_checksum_changed")
        self.assertEqual(info["resolve"], "_resolve_device_dependency")
        self.assertEqual(info["track_fields"], ["os", "group_id", "organization_id"])
        self.assertEqual(info["on_commit"], True)
        self.assertEqual(info["dispatch_uid"], "test.cache_dependency")

    def test_print_cache_dependencies_text(self):
        out = StringIO()
        call_command("print_cache_dependencies", stdout=out)
        output = out.getvalue()
        self.assertIn("update_status_if_checksum_changed", output)
        self.assertIn("on_commit", output)
        self.assertIn("uid:", output)

    def test_print_cache_dependencies_json(self):
        out = StringIO()
        call_command("print_cache_dependencies", format="json", stdout=out)
        data = json.loads(out.getvalue())
        self.assertGreater(len(data), 0)
        expected_keys = {
            "source",
            "signal",
            "target",
            "resolve",
            "track_fields",
            "on_create",
            "on_commit",
            "dispatch_uid",
        }
        for item in data:
            self.assertEqual(set(item.keys()), expected_keys)

    def test_invalidate_devicegroup_cache_change_handler_bulk_list(self):
        device_id1, device_id2 = uuid.uuid4(), uuid.uuid4()
        with patch.object(tasks.invalidate_devicegroup_cache_change, "delay") as delay:
            invalidate_devicegroup_cache_change_handler([device_id1, device_id2])
        self.assertEqual(delay.call_count, 2)
        delay.assert_has_calls(
            [
                call(device_id1, Device._meta.model_name),
                call(device_id2, Device._meta.model_name),
            ]
        )
