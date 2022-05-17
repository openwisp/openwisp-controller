from django.core.exceptions import ValidationError
from django.test import TestCase
from swapper import load_model

from .. import settings as app_settings
from .utils import CreateConnectionsMixin

Credentials = load_model('connection', 'Credentials')


class TestSnmp(CreateConnectionsMixin, TestCase):
    def test_create_snmp_connector(self):
        init_credentials_count = Credentials.objects.count()
        params = {'community': 'public', 'agent': 'my-agent', 'port': 161}

        with self.subTest('test openwrt'):
            obj = self._create_credentials(
                params=params, connector=app_settings.CONNECTORS[1][0], auto_add=True
            )
            obj.save()
            obj.connector_instance.validate(params)
            self.assertEqual(params, obj.params)
            self.assertEqual(Credentials.objects.count(), init_credentials_count + 1)
            self.assertEqual(
                obj.connector,
                'openwisp_controller.connection.connectors.openwrt.snmp.OpenWRTSnmp',
            )

        with self.subTest('test airos'):
            obj = self._create_credentials(
                name='airos snmp',
                params=params,
                connector=app_settings.CONNECTORS[2][0],
                auto_add=True,
            )
            obj.save()
            obj.connector_instance.validate(params)
            self.assertEqual(params, obj.params)
            self.assertEqual(Credentials.objects.count(), init_credentials_count + 2)
            self.assertEqual(
                obj.connector,
                'openwisp_controller.connection.connectors.airos.snmp.AirOsSnmp',
            )

    def test_validation(self):
        with self.subTest('test validation unsuccessful'):
            params = {'agent': 'my-agent', 'port': 161}
            with self.assertRaises(ValidationError):
                self._create_credentials(
                    params=params, connector=app_settings.CONNECTORS[1][0]
                )

        with self.subTest('test validation successful'):
            params = {'community': 'public', 'agent': 'my-agent', 'port': 161}
            obj = self._create_credentials(
                params=params, connector=app_settings.CONNECTORS[1][0], auto_add=True
            )
            obj.save()
            obj.connector_instance.validate(params)
