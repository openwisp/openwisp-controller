import io
import json
import os
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db.models.signals import post_save
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import catch_signal

from ...geo.tests.utils import TestGeoMixin
from ...tests.utils import TestAdminMixin
from .. import settings as app_settings
from ..signals import (
    device_group_changed,
    device_name_changed,
    group_templates_changed,
    management_ip_changed,
)
from .utils import (
    CreateConfigTemplateMixin,
    CreateDeviceGroupMixin,
    CreateDeviceMixin,
    TestVpnX509Mixin,
)

devnull = open(os.devnull, 'w')
Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
DeviceGroup = load_model('config', 'DeviceGroup')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')
User = get_user_model()
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
Group = load_model('openwisp_users', 'Group')


class TestImportExportMixin:
    """
    Reused in OpenWISP Monitoring
    """

    resource_fields = [
        'name',
        'mac_address',
        'organization__name',
        'group__name',
        'config__status',
        'config__backend',
        'last_ip',
        'management_ip',
        'created',
        'modified',
        'key',
        'id',
        'organization',
        'group',
    ]

    def test_device_import_export_buttons(self):
        path = reverse(f'admin:{self.app_label}_device_changelist')
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Import</a>')
        self.assertContains(response, 'Export</a>')

    def test_device_export(self):
        response = self.client.post(
            reverse(f'admin:{self.app_label}_device_export'), {'file_format': '0'}
        )
        self.assertNotContains(response, 'error')
        self.assertIsNotNone(response.get('Content-Disposition'))
        file_ = io.BytesIO(response.content)
        csv = file_.getvalue().decode()
        for field in self.resource_fields:
            self.assertIn(field, csv)

    def test_device_import(self):
        org = self._get_org()
        contents = (
            'organization,name,mac_address\n' f'{org.pk},TestImport,00:11:22:09:44:55'
        )
        csv = ContentFile(contents)
        response = self.client.post(
            reverse(f'admin:{self.app_label}_device_import'),
            {'input_format': '0', 'import_file': csv},
        )
        self.assertNotContains(response, 'errorlist')
        self.assertNotContains(response, 'Errors')
        self.assertContains(response, 'Confirm import')


class TestAdmin(
    TestImportExportMixin,
    TestGeoMixin,
    CreateDeviceGroupMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    TestAdminMixin,
    TestOrganizationMixin,
    TestCase,
):
    """
    tests for Config model
    """

    app_label = 'config'
    fixtures = ['test_templates']
    location_model = Location
    object_model = Device
    object_location_model = DeviceLocation
    maxDiff = None
    _device_params = {
        'name': 'test-device',
        'hardware_id': '1234',
        'mac_address': CreateConfigTemplateMixin.TEST_MAC_ADDRESS,
        'key': CreateConfigTemplateMixin.TEST_KEY,
        'model': '',
        'os': '',
        'notes': '',
        'config-0-id': '',
        'config-0-device': '',
        'config-0-backend': 'netjsonconfig.OpenWrt',
        'config-0-templates': '',
        'config-0-config': json.dumps({}),
        'config-0-context': '',
        'config-TOTAL_FORMS': 1,
        'config-INITIAL_FORMS': 0,
        'config-MIN_NUM_FORMS': 0,
        'config-MAX_NUM_FORMS': 1,
        # openwisp_controller.connection
        'deviceconnection_set-TOTAL_FORMS': 0,
        'deviceconnection_set-INITIAL_FORMS': 0,
        'deviceconnection_set-MIN_NUM_FORMS': 0,
        'deviceconnection_set-MAX_NUM_FORMS': 1000,
        'command_set-TOTAL_FORMS': 0,
        'command_set-INITIAL_FORMS': 0,
        'command_set-MIN_NUM_FORMS': 0,
        'command_set-MAX_NUM_FORMS': 1000,
    }
    # WARNING - WATCHOUT
    # this class attribute is changed dynamically
    # by other apps which add inlines to DeviceAdmin
    _additional_params = {}

    def setUp(self):
        self.client.force_login(self._get_admin())

    def _get_device_params(self, org):
        p = self._device_params.copy()
        p.update(self._additional_params)
        p['organization'] = org.pk
        return p

    def test_device_and_template_different_organization(self):
        org1 = self._get_org()
        template = self._create_template(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        config = self._create_config(organization=org2)
        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device.pk])
        # ensure it fails with error
        self._login()
        params = self._get_device_params(org=org2)
        params.update(
            {
                'config-0-id': config.pk,
                'config-0-device': config.device.pk,
                'config-0-templates': template.pk,
                'config-INITIAL_FORMS': 1,
            }
        )
        response = self.client.post(path, params)
        self.assertContains(response, 'errors field-templates')
        # remove conflicting template and ensure doesn't error
        params.update({'config-0-templates': ''})
        response = self.client.post(path, params)
        self.assertNotContains(response, 'errors field-templates', status_code=302)

    def test_add_device(self):
        org1 = self._get_org()
        t1 = self._create_template(name='t1', organization=org1)
        t2 = self._create_template(name='t2', organization=None)
        path = reverse(f'admin:{self.app_label}_device_add')
        data = self._get_device_params(org=org1)
        data.update(
            {
                'name': 'testadd',
                'config-0-templates': ','.join([str(t1.pk), str(t2.pk)]),
            }
        )
        self._login()
        self.client.post(path, data)
        queryset = Device.objects.filter(name='testadd')
        self.assertEqual(queryset.count(), 1)
        device = queryset.first()
        self.assertEqual(device.config.templates.count(), 2)
        self.assertEqual(
            device.config.templates.filter(name__in=['t1', 't2']).count(), 2
        )

    def test_add_device_does_not_emit_changed_signals(self):
        org1 = self._get_org()
        path = reverse(f'admin:{self.app_label}_device_add')
        data = self._get_device_params(org=org1)
        data.update({'group': str(self._create_device_group().pk)})
        self._login()
        with catch_signal(
            device_group_changed
        ) as mocked_device_group_changed, catch_signal(
            device_name_changed
        ) as mocked_device_name_changed, catch_signal(
            management_ip_changed
        ) as mocked_management_ip_changed:
            self.client.post(path, data)

        mocked_device_group_changed.assert_not_called()
        mocked_device_name_changed.assert_not_called()
        mocked_management_ip_changed.assert_not_called()

    def test_preview_device(self):
        org = self._get_org()
        self._create_template(organization=org)
        templates = Template.objects.all()
        path = reverse(f'admin:{self.app_label}_device_preview')
        config = json.dumps(
            {
                'interfaces': [
                    {
                        'name': 'eth0',
                        'type': 'ethernet',
                        'addresses': [{'family': 'ipv4', 'proto': 'dhcp'}],
                    }
                ]
            }
        )
        data = {
            'name': 'test-device',
            'organization': org.pk,
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'csrfmiddlewaretoken': 'test',
            'templates': ','.join([str(t.pk) for t in templates]),
        }
        self._login()
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, 'eth0')
        self.assertContains(response, 'dhcp')

    def test_device_preview_button(self):
        config = self._create_config(organization=self._get_org())
        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def test_template_preview_button(self):
        t = self._create_template(organization=self._get_org())
        path = reverse(f'admin:{self.app_label}_template_change', args=[t.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def test_vpn_preview_button(self):
        v = self._create_vpn(organization=self._get_org())
        path = reverse(f'admin:{self.app_label}_vpn_change', args=[v.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def _create_multitenancy_test_env(self, vpn=False):
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        inactive = self._create_org(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        administrator = self._create_administrator(organizations=[org1, inactive])
        t1 = self._create_template(name='template1org', organization=org1)
        t2 = self._create_template(name='template2org', organization=org2)
        t3 = self._create_template(name='t3-inactive', organization=inactive)
        d1 = self._create_device(name='org1-config', organization=org1)
        c1 = self._create_config(device=d1)
        d2 = self._create_device(
            name='org2-config',
            organization=org2,
            key='ke1',
            mac_address='00:11:22:33:44:56',
        )
        c2 = self._create_config(device=d2)
        d3 = self._create_device(
            name='config-inactive',
            organization=inactive,
            key='key2',
            mac_address='00:11:22:33:44:57',
        )
        c3 = self._create_config(device=d3)
        c1.templates.add(t1)
        c2.templates.add(t2)
        data = dict(
            c1=c1,
            c2=c2,
            c3_inactive=c3,
            t1=t1,
            t2=t2,
            t3_inactive=t3,
            org1=org1,
            org2=org2,
            inactive=inactive,
            operator=operator,
            administrator=administrator,
        )
        if vpn:
            v1 = self._create_vpn(name='vpn1org', organization=org1)
            v2 = self._create_vpn(name='vpn2org', organization=org2)
            v3 = self._create_vpn(name='vpn3shared', organization=None)
            v4 = self._create_vpn(name='vpn4inactive', organization=inactive)
            t4 = self._create_template(
                name='vpn-template1org', organization=org1, type='vpn', vpn=v1
            )
            data.update(
                dict(vpn1=v1, vpn2=v2, vpn_shared=v3, vpn_inactive=v4, t1_vpn=t4)
            )
        return data

    def test_device_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_device_changelist'),
            visible=[data['c1'].name, data['org1'].name],
            hidden=[data['c2'].name, data['org2'].name, data['c3_inactive'].name],
        )

    def test_device_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(
                self.app_label, 'device', 'organization'
            ),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive'].name],
        )

    def test_device_templates_m2m_queryset(self):
        data = self._create_multitenancy_test_env()
        t_shared = self._create_template(name='t-shared', organization=None)
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_device_add'),
            visible=[str(data['t1']), str(t_shared)],
            hidden=[str(data['t2']), str(data['t3_inactive'])],
        )

    def test_template_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_template_changelist'),
            visible=[data['t1'].name, data['org1'].name],
            hidden=[data['t2'].name, data['org2'].name, data['t3_inactive'].name],
        )

    def test_template_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(
                self.app_label, 'template', 'organization'
            ),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive'].name],
        )

    def test_template_vpn_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(self.app_label, 'template', 'vpn'),
            visible=[data['vpn1'].name],
            hidden=[data['vpn2'].name, data['vpn_inactive'].name],
        )

    def test_vpn_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_vpn_changelist'),
            visible=[data['org1'].name, data['vpn1'].name],
            hidden=[
                data['org2'].name,
                data['inactive'],
                data['vpn2'].name,
                data['vpn_shared'].name,
                data['vpn_inactive'].name,
            ],
        )

    def test_vpn_organization_fk_autocomplete_view(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(self.app_label, 'vpn', 'organization'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            administrator=True,
        )

    def test_vpn_ca_fk_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_vpn_add'),
            visible=[data['vpn1'].ca.name, data['vpn_shared'].ca.name],
            hidden=[data['vpn2'].ca.name, data['vpn_inactive'].ca.name],
            select_widget=True,
            administrator=True,
        )

    def test_vpn_cert_fk_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_vpn_add'),
            visible=[data['vpn1'].cert.name, data['vpn_shared'].cert.name],
            hidden=[data['vpn2'].cert.name, data['vpn_inactive'].cert.name],
            select_widget=True,
            administrator=True,
        )

    def test_changelist_recover_deleted_button(self):
        self._create_multitenancy_test_env()
        self._test_changelist_recover_deleted(self.app_label, 'device')
        self._test_changelist_recover_deleted(self.app_label, 'template')
        self._test_changelist_recover_deleted(self.app_label, 'vpn')

    def test_recoverlist_operator_403(self):
        self._create_multitenancy_test_env()
        self._test_recoverlist_operator_403(self.app_label, 'device')
        self._test_recoverlist_operator_403(self.app_label, 'template')
        self._test_recoverlist_operator_403(self.app_label, 'vpn')

    def test_device_template_filter(self):
        org = self._get_org(org_name='test-org')
        t = self._create_template(name='test-template', organization=org)
        d1 = self._create_device(
            name='test-device1',
            organization=org,
            mac_address='00:11:22:33:44:56',
        )
        d2 = self._create_device(
            name='test-device2',
            organization=org,
            mac_address='00:11:22:33:44:57',
        )
        c = self._create_config(device=d1)
        c.templates.add(t)
        url = reverse(f'admin:{self.app_label}_device_changelist')
        query = f'?config__templates={t.pk}'
        response = self.client.get(f'{url}{query}')
        self.assertContains(response, d1.name)
        self.assertNotContains(response, d2.name)

    def _get_change_device_post_data(self, device):
        return {
            '_selected_action': [device.pk],
            'action': 'change_group',
            'csrfmiddlewaretoken': 'test',
        }

    def test_change_device_group_action(self):
        path = reverse(f'admin:{self.app_label}_device_changelist')
        org = self._get_org(org_name='default')
        device = self._create_device(organization=org)
        post_data = self._get_change_device_post_data(device)
        response = self.client.post(path, post_data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, 'What group do you want to assign to the selected devices?'
        )

    def test_device_import_with_group_apply_templates(self):
        org = self._get_org(org_name='default')
        template = self._create_template(name='template')
        dg = self._create_device_group(name='test-group', organization=org)
        dg.templates.add(template)
        contents = (
            'organization,name,mac_address,group\n'
            f'{org.pk},TestImport,00:11:22:09:44:55,{dg.pk}'
        )
        csv = ContentFile(contents)
        response = self.client.post(
            reverse(f'admin:{self.app_label}_device_import'),
            {'input_format': '0', 'import_file': csv, 'file_name': 'test.csv'},
        )
        self.assertFalse(response.context['result'].has_errors())
        self.assertIn('confirm_form', response.context)
        confirm_form = response.context['confirm_form']
        data = confirm_form.initial
        response = self.client.post(
            reverse(f'admin:{self.app_label}_device_process_import'), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        device = Device.objects.first()
        self.assertIsNotNone(device)
        self.assertEqual(device.group, dg)
        self.assertIsNotNone(device.config)
        self.assertIn(template, device.config.templates.all())

    def test_add_device_with_group_templates(self):
        org = self._get_org(org_name='default')
        t1 = self._create_template(name='t1')
        t2 = self._create_template(name='t2')
        dg1 = self._create_device_group(name='test-group-1', organization=org)
        dg1.templates.add(t1)
        dg2 = self._create_device_group(name='test-group-2', organization=org)
        dg2.templates.add(t2)
        data = self._get_device_params(org=org)
        data.update(group=str(dg1.pk))
        with catch_signal(post_save) as mock_post_save, catch_signal(
            device_group_changed
        ) as device_group_changed_mock:
            self.client.post(
                reverse(f'admin:{self.app_label}_device_add'), data, follow=True
            )
        device = Device.objects.first()
        mock_post_save.assert_any_call(
            signal=post_save,
            sender=Config,
            instance=device.config,
            created=True,
            update_fields=None,
            raw=False,
            using='default',
        )
        device_group_changed_mock.assert_not_called()
        self.assertIn(t1, device.config.templates.all())

    def test_unassigning_group_removes_old_templates(self):
        org = self._get_org(org_name='default')
        template = self._create_template(name='template')
        dg = self._create_device_group(name='test-group', organization=org)
        dg.templates.add(template)
        device = self._create_device(organization=org, group=dg)
        self.assertIn(template, device.config.templates.all())
        path = reverse(f'admin:{self.app_label}_device_change', args=[device.pk])
        params = self._get_device_params(org=org)
        params.update(
            {
                'name': 'test-device-changed',
                'config-0-id': str(device.config.pk),
                'config-0-device': str(device.pk),
                'config-INITIAL_FORMS': 1,
                'group': '',
            }
        )
        response = self.client.post(path, params, follow=True)
        self.assertNotContains(response, 'errors', status_code=200)
        device.refresh_from_db()
        self.assertIsNone(device.group)
        self.assertNotIn(template, device.config.templates.all())

    def test_group_templates_are_not_forced(self):
        o = self._get_org()
        t = self._create_template(name='t')
        dg = self._create_device_group(name='test-group', organization=o)
        dg.templates.add(t)
        d = self._create_device(organization=o, group=dg)
        self.assertIn(t, d.config.templates.all())
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        params = self._get_device_params(org=o)
        params.update(
            {
                'name': 'test-device-changed',
                'config-0-id': str(d.config.pk),
                'config-0-device': str(d.pk),
                'config-0-templates': '',
                'config-INITIAL_FORMS': 1,
                'group': str(dg.pk),
            }
        )
        response = self.client.post(path, params)
        self.assertNotContains(response, 'errors', status_code=302)
        d.refresh_from_db()
        self.assertEqual(d.config.name, 'test-device-changed')
        self.assertFalse(d.config.templates.filter(pk=t.pk).exists())

    def test_device_contains_default_templates_js(self):
        config = self._create_config(organization=self._get_org())
        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device.pk])
        self._login()
        response = self.client.get(path)
        self.assertContains(response, '// enable default templates')

    def test_template_not_contains_default_templates_js(self):
        template = self._create_template()
        path = reverse(f'admin:{self.app_label}_template_change', args=[template.pk])
        self._login()
        response = self.client.get(path)
        self.assertNotContains(response, '// enable default templates')

    def test_configuration_templates_removed(self):
        def _update_template(templates):
            params.update(
                {
                    'config-0-templates': ','.join(
                        [str(template.pk) for template in templates]
                    )
                }
            )
            response = self.client.post(path, data=params, follow=True)
            self.assertEqual(response.status_code, 200)
            for template in templates:
                self.assertContains(
                    response, f'class="sortedm2m" checked> {template.name}'
                )
            return response

        template = self._create_template()

        # Add a new device
        path = reverse(f'admin:{self.app_label}_device_add')
        params = self._get_device_params(org=self._get_org())
        response = self.client.post(path, data=params, follow=True)
        self.assertEqual(response.status_code, 200)

        config = Device.objects.get(name=params['name']).config
        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device_id])
        params.update(
            {
                'config-0-id': str(config.pk),
                'config-0-device': str(config.device_id),
                'config-INITIAL_FORMS': 1,
                '_continue': True,
            }
        )

        # Add template to the device
        _update_template(templates=[template])
        config.refresh_from_db()
        self.assertEqual(config.templates.count(), 1)
        self.assertEqual(config.status, 'modified')
        config.set_status_applied()
        self.assertEqual(config.status, 'applied')

        # Remove template from the device
        _update_template(templates=[])
        config.refresh_from_db()
        self.assertEqual(config.templates.count(), 0)
        self.assertEqual(config.status, 'modified')

    def test_vpn_not_contains_default_templates_js(self):
        vpn = self._create_vpn()
        path = reverse(f'admin:{self.app_label}_vpn_change', args=[vpn.pk])
        self._login()
        response = self.client.get(path)
        self.assertNotContains(response, '// enable default templates')

    def _get_clone_template_post_data(self, template):
        return {
            '_selected_action': [template.pk],
            'action': 'clone_selected_templates',
            'csrfmiddlewaretoken': 'test',
        }

    def test_clone_templates_superuser_1_org(self):
        path = reverse(f'admin:{self.app_label}_template_changelist')
        t = self._create_template(organization=self._get_org(org_name='default'))
        post_data = self._get_clone_template_post_data(t)
        self.client.force_login(self._get_admin())
        response = self.client.post(path, post_data, follow=True)
        self.assertContains(response, '{} (Clone)'.format(t.name))

    def test_clone_templates_superuser_multi_orgs(self):
        path = reverse(f'admin:{self.app_label}_template_changelist')
        t = self._create_template(organization=self._get_org('org_2'))
        post_data = self._get_clone_template_post_data(t)
        self.client.force_login(self._get_admin())
        response = self.client.post(path, post_data)
        self.assertContains(response, 'Clone templates')
        self.assertContains(response, 'Shared systemwide')

    def test_clone_templates_operator_1_org(self):
        path = reverse(f'admin:{self.app_label}_template_changelist')
        t = self._create_template(organization=self._get_org())
        test_user = self._create_operator(organizations=[self._get_org()])
        post_data = self._get_clone_template_post_data(t)
        self.client.force_login(test_user)
        response = self.client.post(path, post_data, follow=True)
        self.assertContains(response, '{} (Clone)'.format(t.name))

    def test_clone_templates_operator_multi_orgs(self):
        path = reverse(f'admin:{self.app_label}_template_changelist')
        t = self._create_template()
        post_data = self._get_clone_template_post_data(t)
        operator = self._create_operator(
            organizations=[self._get_org(), self._get_org('org_2')]
        )
        self.client.force_login(operator)
        response = self.client.post(path, post_data)
        self.assertContains(response, 'Clone templates')
        self.assertNotContains(response, 'Shared systemwide')

    def test_change_device_clean_templates(self):
        o = self._get_org()
        t = Template.objects.first()
        d = self._create_device(organization=o)
        c = self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        params = self._get_device_params(org=o)
        params.update(
            {
                'name': 'test-change-device',
                'config-0-id': str(c.pk),
                'config-0-device': str(d.pk),
                'config-0-templates': str(t.pk),
                'config-INITIAL_FORMS': 1,
            }
        )
        # ensure it fails with error
        with patch.object(
            Config, 'clean_templates', side_effect=ValidationError('test')
        ):
            response = self.client.post(path, params)
        self.assertContains(response, 'errors field-templates')
        # remove conflicting template and ensure doesn't error
        params['config-0-templates'] = ''
        response = self.client.post(path, params)
        self.assertNotContains(response, 'errors field-templates', status_code=302)

    def test_change_device_required_template(self):
        o = self._get_org()
        t = Template.objects.first()
        t.name = 'Empty'
        t.config = {'interfaces': []}
        t.required = True
        t.full_clean()
        t.save()
        d = self._create_device(organization=o)
        c = self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])

        with self.subTest(
            'POST request without a required template is ineffective in removing it'
        ):
            t2 = Template.objects.get(name='radio0')
            params = self._get_device_params(org=o)
            params.update(
                {
                    'name': 'test-device-changed',
                    'config-0-id': str(c.pk),
                    'config-0-device': str(d.pk),
                    'config-0-templates': str(t2.pk),
                    'config-INITIAL_FORMS': 1,
                }
            )
            response = self.client.post(path, params)
            self.assertNotContains(response, 'errors', status_code=302)
            c.refresh_from_db()
            self.assertEqual(c.name, 'test-device-changed')
            self.assertTrue(c.templates.filter(pk=t.pk).exists())

        with self.subTest(
            'Clearing all templates is ineffective in removing required template'
        ):
            params = self._get_device_params(org=o)
            params.update(
                {
                    'name': 'test-device-templates-cleared',
                    'config-0-id': str(c.pk),
                    'config-0-device': str(d.pk),
                    'config-0-templates': '',
                    'config-INITIAL_FORMS': 1,
                }
            )
            response = self.client.post(path, params)
            self.assertNotContains(response, 'errors', status_code=302)
            c.refresh_from_db()
            self.assertEqual(c.name, 'test-device-templates-cleared')
            self.assertTrue(c.templates.filter(pk=t.pk).exists())

    def test_change_device_org_required_templates(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        template = self._create_template(organization=org1, config={'interfaces': []})
        device = self._create_device(organization=org1)
        config = self._create_config(device=device)
        path = reverse(f'admin:{self.app_label}_device_change', args=[device.pk])
        params = self._get_device_params(org=org1)
        params.update(
            {
                'name': 'test-device-changed',
                'config-0-id': str(config.pk),
                'config-0-device': str(device.pk),
                'config-0-templates': str(template.pk),
                'config-INITIAL_FORMS': 1,
                'organization': str(org2.pk),
            }
        )
        response = self.client.post(path, params, follow=True)
        self.assertEqual(response.status_code, 200)
        config.refresh_from_db()
        self.assertEqual(config.templates.count(), 0)

    def test_download_device_config(self):
        d = self._create_device(name='download')
        self._create_config(device=d)
        path = reverse(f'admin:{self.app_label}_device_download', args=[d.pk.hex])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('content-type'), 'application/octet-stream')

    def test_download_device_config_404(self):
        d = self._create_device(name='download')
        path = reverse(f'admin:{self.app_label}_device_download', args=[d.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    @patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', True)
    def test_preview_device_config(self):
        templates = Template.objects.all()
        path = reverse(f'admin:{self.app_label}_device_preview')
        config = json.dumps(
            {
                'general': {'description': '{{hardware_id}}'},
                'interfaces': [
                    {
                        'name': 'lo0',
                        'type': 'loopback',
                        'addresses': [
                            {
                                'family': 'ipv4',
                                'proto': 'static',
                                'address': '127.0.0.1',
                                'mask': 8,
                            }
                        ],
                    }
                ],
            }
        )
        data = {
            'name': 'test-device',
            'hardware_id': 'SERIAL012345',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'context': '',
            'csrfmiddlewaretoken': 'test',
            'templates': ','.join([str(t.pk) for t in templates]),
        }
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, 'lo0')
        self.assertContains(response, 'eth0')
        self.assertContains(response, 'dhcp')
        self.assertContains(response, 'radio0')
        self.assertContains(response, 'SERIAL012345')

    def test_variable_usage(self):
        config = {
            'interfaces': [
                {
                    'name': 'lo0',
                    'type': 'loopback',
                    'mac_address': '{{ mac }}',
                    'addresses': [
                        {
                            'family': 'ipv4',
                            'proto': 'static',
                            'address': '{{ ip }}',
                            'mask': 8,
                        }
                    ],
                }
            ]
        }
        default_values = {'ip': '192.168.56.2', 'mac': '08:00:27:06:72:88'}
        t = self._create_template(config=config, default_values=default_values)
        path = reverse(f'admin:{self.app_label}_device_add')
        params = self._get_device_params(org=self._get_org())
        params.update({'name': 'test-device', 'config-0-templates': str(t.pk)})
        response = self.client.post(path, params)
        self.assertNotContains(response, 'errors field-templates', status_code=302)
        self.assertEqual(Device.objects.filter(name='test-device').count(), 1)

    def test_preview_device_config_empty_id(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        config = json.dumps({'general': {'descripion': 'id: {{ id }}'}})
        data = {
            'id': '',
            'name': 'test-empty-id',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        # expect 200
        self.assertContains(response, 'id:')

    def test_preview_device_attributeerror(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        data = {
            'name': 'test-device',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': '{}',
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')

    @patch('sys.stdout', devnull)
    @patch('sys.stderr', devnull)
    def test_preview_device_valueerror(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        data = {
            'name': 'test-device',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': '{}',
            'templates': 'wrong,totally',
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 400)

    @patch('sys.stdout', devnull)
    @patch('sys.stderr', devnull)
    def test_preview_device_validationerror(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        data = {
            'name': 'test-device',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': '{"interfaces": {"wrong":"wrong"}}',
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 400)

    @patch('sys.stdout', devnull)
    @patch('sys.stderr', devnull)
    def test_preview_device_jsonerror(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        data = {
            'name': 'test-device',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': 'WRONG',
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertEqual(response.status_code, 400)

    def test_preview_device_showerror(self):
        t1 = Template.objects.get(name='dhcp')
        t2 = Template(name='t2', config=t1.config, backend=t1.backend)
        t3 = Template(name='t3', config=t1.config, backend=t1.backend)
        t4 = Template(
            name='t4',
            config={"interfaces": [{"name": "eth0", "type": "bridge", "stp": "WRONG"}]},
            backend='netjsonconfig.OpenWrt',
        )
        # skip validating config to raise error later
        t4.save()
        # adding multiple templates to ensure the order is retained correctly
        templates = [t1, t2, t3, t4]
        path = reverse(f'admin:{self.app_label}_device_preview')
        data = {
            'name': 'test-device',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': '{}',
            'templates': ','.join([str(t.pk) for t in templates]),
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        # expect error
        self.assertContains(response, '<pre class="djnjc-preformatted error')

    @patch('sys.stdout', devnull)
    @patch('sys.stderr', devnull)
    def test_preview_device_405(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        response = self.client.get(path, {})
        self.assertEqual(response.status_code, 405)

    def test_config_error_reason(self):
        device = self._create_device(name='download')
        config = self._create_config(device=device)
        url = reverse(f'admin:{self.app_label}_device_change', args=[device.pk])

        with self.subTest('Test config status "modified" or "applied"'):
            self.assertEqual(config.status, 'modified')
            response = self.client.get(url)
            self.assertNotContains(response, '<label>Error reason:</label>', html=True)
            config.set_status_applied()
            response = self.client.get(url)
            self.assertNotContains(response, '<label>Error reason:</label>', html=True)

        with self.subTest('Test config status "error"'):
            config.set_status_error(reason='Reason not reported by the device.')
            response = self.client.get(url)
            self.assertContains(response, '<label>Error reason:</label>', html=True)
            self.assertContains(
                response,
                '<div class="readonly">Reason not reported by the device.</div>',
                html=True,
            )

        with self.subTest('Test regression status "applied" after "error"'):
            config.set_status_applied()
            self.assertEqual(config.status, 'applied')
            response = self.client.get(url)
            self.assertNotContains(response, '<label>Error reason:</label>', html=True)

    def test_download_template_config(self):
        t = Template.objects.first()
        path = reverse(f'admin:{self.app_label}_template_download', args=[t.pk])
        response = self.client.get(path)
        self.assertEqual(response.get('content-type'), 'application/octet-stream')

    def test_template_has_download_config(self):
        t = Template.objects.first()
        path = reverse(f'admin:{self.app_label}_template_change', args=[t.pk])
        r = self.client.get(path)
        self.assertContains(r, 'Download configuration')

    def test_preview_template(self):
        template = Template.objects.get(name='radio0')
        path = reverse(f'admin:{self.app_label}_template_preview')
        data = {
            'name': template.name,
            'backend': template.backend,
            'config': json.dumps(template.config),
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, 'radio0')
        self.assertContains(response, 'phy')
        self.assertNotContains(response, 'system')
        self.assertNotContains(response, 'hostname')

    def test_change_device_404(self):
        path = reverse(f'admin:{self.app_label}_device_change', args=[Device().pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    def test_change_device_malformed_uuid(self):
        path = reverse(
            f'admin:{self.app_label}_device_change',
            args=['00000000-0000-0000-0000-000000000000'],
        )
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

    def test_uuid_field_in_change(self):
        t = Template.objects.first()
        d = self._create_device()
        c = self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[c.device.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'field-uuid')

    def test_empty_backend_import_error(self):
        t = Template.objects.first()
        path = reverse(f'admin:{self.app_label}_device_add')
        params = self._get_device_params(org=self._get_org())
        params.update(
            {
                'name': 'empty-backend',
                'key': self.TEST_KEY,
                'config-0-templates': str(t.pk),
                'config-0-backend': '',
                'config-0-config': json.dumps({'general': {'hostname': 'config'}}),
            }
        )
        response = self.client.post(path, params)
        self.assertContains(response, 'errors field-backend')

    def test_default_device_backend(self):
        path = reverse(f'admin:{self.app_label}_device_add')
        response = self.client.get(path)
        self.assertContains(response, '<option value="netjsonconfig.OpenWrt" selected')

    def test_existing_device_backend(self):
        d = self._create_device()
        self._create_config(device=d, backend='netjsonconfig.OpenWisp')
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        response = self.client.get(path)
        self.assertContains(response, '<option value="netjsonconfig.OpenWisp" selected')

    def test_device_search(self):
        d = self._create_device(name='admin-search-test')
        path = reverse(f'admin:{self.app_label}_device_changelist')
        response = self.client.get(path, {'q': str(d.pk.hex)})
        self.assertContains(response, 'admin-search-test')
        response = self.client.get(path, {'q': 'ZERO-RESULTS-PLEASE'})
        self.assertNotContains(response, 'admin-search-test')

        with self.subTest('test device location search'):
            response = self.client.get(path, {'q': 'Estonia'})
            self.assertNotContains(response, 'admin-search-test')
            location = self._create_location(
                name='OW2',
                address='Sepapaja 35, Tallinn, Estonia',
                organization=self._get_org(),
            )
            self._create_object_location(content_object=d, location=location)
            response = self.client.get(path, {'q': 'Estonia'})
            self.assertContains(response, 'admin-search-test')

    def test_default_template_backend(self):
        path = reverse(f'admin:{self.app_label}_template_add')
        response = self.client.get(path)
        self.assertContains(response, '<option value="netjsonconfig.OpenWrt" selected')

    def test_existing_template_backend(self):
        t = Template.objects.first()
        t.backend = 'netjsonconfig.OpenWisp'
        t.save()
        path = reverse(f'admin:{self.app_label}_template_change', args=[t.pk])
        response = self.client.get(path)
        self.assertContains(response, '<option value="netjsonconfig.OpenWisp" selected')

    def test_preview_variables(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        c = self._create_config(
            device=self._create_device(name='variables'),
            config={
                'general': {
                    'cid': '{{ id }}',
                    'ckey': '{{ key }}',
                    'cname': '{{ name }}',
                }
            },
        )
        templates = Template.objects.all()
        c.templates.add(*templates)
        d = c.device
        data = {
            'name': d.name,
            'id': d.id,
            'mac_address': d.mac_address,
            'key': d.key,
            'backend': c.backend,
            'config': json.dumps(c.config),
            'csrfmiddlewaretoken': 'test',
            'templates': ','.join([str(t.pk) for t in templates]),
        }
        response = self.client.post(path, data)
        response_html = response.content.decode('utf8')
        self.assertTrue(
            any(
                [
                    "cid &#39;{0}&#39;".format(str(d.id)) in response_html,
                    # django >= 3.0
                    "cid &#x27;{0}&#x27;".format(str(d.id)) in response_html,
                ]
            )
        )
        self.assertTrue(
            any(
                [
                    "ckey &#39;{0}&#39;".format(str(d.key)) in response_html,
                    # django >= 3.0
                    "ckey &#x27;{0}&#x27;".format(str(d.key)) in response_html,
                ]
            )
        )
        self.assertTrue(
            any(
                [
                    "cname &#39;{0}&#39;".format(str(d.name)) in response_html,
                    # django >= 3.0
                    "cname &#x27;{0}&#x27;".format(str(d.name)) in response_html,
                ]
            )
        )

    def test_download_vpn_config(self):
        v = self._create_vpn()
        path = reverse(f'admin:{self.app_label}_vpn_download', args=[v.pk])
        response = self.client.get(path)
        self.assertEqual(response.get('content-type'), 'application/octet-stream')

    def test_vpn_has_download_config(self):
        v = self._create_vpn()
        path = reverse(f'admin:{self.app_label}_vpn_change', args=[v.pk])
        r = self.client.get(path)
        self.assertContains(r, 'Download configuration')

    def test_preview_vpn(self):
        v = self._create_vpn()
        path = reverse(f'admin:{self.app_label}_vpn_preview')
        data = {
            'name': v.name,
            'backend': v.backend,
            'host': v.host,
            'ca': v.ca_id,
            'cert': v.cert_id,
            'config': json.dumps(v.config),
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, '# openvpn config:')

    def test_add_vpn(self):
        path = reverse(f'admin:{self.app_label}_vpn_add')
        response = self.client.get(path)
        self.assertContains(
            response, 'value="openwisp_controller.vpn_backends.OpenVpn" selected'
        )

    def test_vpn_clients_deleted(self):
        def _update_template(templates):
            params.update(
                {
                    'config-0-templates': ','.join(
                        [str(template.pk) for template in templates]
                    )
                }
            )
            response = self.client.post(path, data=params, follow=True)
            self.assertEqual(response.status_code, 200)
            for template in templates:
                self.assertContains(
                    response, f'class="sortedm2m" checked> {template.name}'
                )
            return response

        vpn = self._create_vpn()
        template = self._create_template()
        vpn_template = self._create_template(
            name='vpn-test',
            type='vpn',
            vpn=vpn,
            auto_cert=True,
        )
        cert_query = Cert.objects.exclude(pk=vpn.cert_id)

        # Add a new device
        path = reverse(f'admin:{self.app_label}_device_add')
        params = self._get_device_params(org=self._get_org())
        response = self.client.post(path, data=params, follow=True)
        self.assertEqual(response.status_code, 200)

        config = Device.objects.get(name=params['name']).config
        self.assertEqual(config.vpnclient_set.count(), 0)
        self.assertEqual(config.templates.count(), 0)

        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device_id])
        params.update(
            {
                'config-0-id': str(config.pk),
                'config-0-device': str(config.device_id),
                'config-INITIAL_FORMS': 1,
                '_continue': True,
            }
        )

        with self.subTest('Adding only VpnClient template'):
            # Adding VpnClient template to the device
            _update_template(templates=[vpn_template])

            self.assertEqual(config.templates.count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 1)
            self.assertEqual(cert_query.count(), 1)

            # Remove VpnClient template from the device
            _update_template(templates=[])

            self.assertEqual(config.templates.count(), 0)
            self.assertEqual(config.vpnclient_set.count(), 0)
            self.assertEqual(cert_query.count(), 0)

        with self.subTest('Add VpnClient template along with another template'):
            # Adding templates to the device
            _update_template(templates=[template, vpn_template])

            self.assertEqual(config.templates.count(), 2)
            self.assertEqual(config.vpnclient_set.count(), 1)
            self.assertEqual(cert_query.count(), 1)

            # Remove VpnClient template from the device
            _update_template(templates=[template])

            self.assertEqual(config.templates.count(), 1)
            self.assertEqual(config.vpnclient_set.count(), 0)
            self.assertEqual(cert_query.count(), 0)

    def test_ip_not_in_add_device(self):
        path = reverse(f'admin:{self.app_label}_device_add')
        response = self.client.get(path)
        self.assertNotContains(response, 'last_ip')

    def test_ip_in_change_device(self):
        d = self._create_device()
        t = Template.objects.first()
        self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        response = self.client.get(path)
        self.assertContains(response, 'last_ip')

    @patch('openwisp_controller.config.settings.HARDWARE_ID_ENABLED', True)
    def test_hardware_id_in_change_device(self):
        d = self._create_device()
        t = Template.objects.first()
        self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        response = self.client.get(path)
        self.assertContains(response, 'hardware_id')

    def test_error_if_download_config(self):
        d = self._create_device()
        res = self.client.get(
            reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        )
        self.assertNotContains(res, 'Download configuration')

    def test_device_has_download_config(self):
        d = self._create_device()
        t = Template.objects.first()
        self._create_config(device=d, backend=t.backend, config=t.config)
        path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
        r = self.client.get(path)
        self.assertContains(r, 'Download configuration')

    def test_preview_device_with_context(self):
        path = reverse(f'admin:{self.app_label}_device_preview')
        config = json.dumps(
            {
                'openwisp': [
                    {
                        'config_name': 'controller',
                        'config_value': 'http',
                        'url': 'http://controller.examplewifiservice.com',
                        'interval': '{{ interval }}',
                        'verify_ssl': '1',
                        'uuid': 'UUID',
                        'key': self.TEST_KEY,
                    }
                ]
            }
        )
        data = {
            'id': 'd60ecd62-5d00-4e7b-bd16-6fc64a95e60c',
            'name': 'test-asd',
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'csrfmiddlewaretoken': 'test',
            'context': '{"interval": "60"}',
        }
        response = self.client.post(path, data)
        response_html = response.content.decode('utf8')
        self.assertTrue(
            any(
                [
                    "option interval &#39;60&#39;" in response_html,
                    # django >= 3.0
                    "option interval &#x27;60&#x27;" in response_html,
                ]
            )
        )

    def test_context_device(self):
        device = self._create_device()
        url = reverse(f'admin:{self.app_label}_device_context', args=[device.pk])
        response = self.client.get(url)
        self.assertEqual(response.json(), device.get_context())
        self.assertEqual(response.status_code, 200)

    def test_context_user_not_authenticated(self):
        self.client.logout()
        device = self._create_device()
        url = reverse(f'admin:{self.app_label}_device_context', args=[device.pk])
        response = self.client.get(url)
        expected_url = '{}?next={}'.format(reverse('admin:login'), url)
        self.assertRedirects(response, expected_url)

    @patch('sys.stdout', devnull)
    @patch('sys.stderr', devnull)
    def test_context_vpn(self):
        vpn = self._create_vpn()
        url = reverse(f'admin:{self.app_label}_vpn_context', args=[vpn.pk])
        response = self.client.get(url)
        self.assertEqual(response.json(), vpn.get_context())
        self.assertEqual(response.status_code, 200)

    def test_context_template(self):
        template = self._create_template()
        url = reverse(f'admin:{self.app_label}_template_context', args=[template.pk])
        response = self.client.get(url)
        self.assertEqual(response.json(), template.get_context())
        self.assertEqual(response.status_code, 200)

    def test_clone_template(self):
        path = reverse(f'admin:{self.app_label}_template_changelist')
        t = self._create_template()
        data = {
            '_selected_action': [t.pk],
            'action': 'clone_selected_templates',
            'csrfmiddlewaretoken': 'test',
        }
        response = self.client.post(path, data, follow=True)
        self.assertContains(response, '{} (Clone)'.format(t.name))
        response = self.client.post(path, data, follow=True)
        self.assertContains(response, '{} (Clone 2)'.format(t.name))
        response = self.client.post(path, data, follow=True)
        self.assertContains(response, '{} (Clone 3)'.format(t.name))
        path = reverse('admin:index')
        response = self.client.get(path)
        self.assertIn('test-template (Clone 3)', str(response.content))
        self.assertIn('test-template (Clone 2)', str(response.content))
        self.assertIn('test-template (Clone)', str(response.content))
        self.assertEqual(LogEntry.objects.all().count(), 3)

    def test_get_template_default_values(self):
        t1 = self._create_template(name='t1', default_values={'name1': 'test1'})
        path = reverse('admin:get_template_default_values')

        with self.subTest('get default values for one template'):
            with self.assertNumQueries(3):
                r = self.client.get(path, {'pks': f'{t1.pk}'})
                self.assertEqual(r.status_code, 200)
                expected = {'default_values': {'name1': 'test1'}}
                self.assertEqual(r.json(), expected)

        with self.subTest('get default values for multiple templates'):
            t2 = self._create_template(name='t2', default_values={'name2': 'test2'})
            with self.assertNumQueries(3):
                r = self.client.get(path, {'pks': f'{t1.pk},{t2.pk}'})
                self.assertEqual(r.status_code, 200)
                expected = {'default_values': {'name1': 'test1', 'name2': 'test2'}}
                self.assertEqual(r.json(), expected)

    def test_get_template_default_values_invalid_pks(self):
        path = reverse('admin:get_template_default_values')
        expected = {'error': 'invalid template pks were received'}

        with self.subTest('test with invalid pk'):
            r = self.client.get(path, {'pks': 'invalid'})
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json(), expected)

        with self.subTest('test with absent pk'):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.json(), expected)

    def _test_system_context_field_helper(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'System Defined Variables')
        self.assertContains(r, '<script id="system_context" type="application/json">')

    def test_system_context(self):
        t = self._create_template()
        d = self._create_device()
        v = self._create_vpn()
        self._create_config(device=d, config=t.config)
        d.refresh_from_db()

        with self.subTest('test field present in template add form'):
            path = reverse(f'admin:{self.app_label}_template_add')
            self._test_system_context_field_helper(path)

        with self.subTest('test field present in template change form'):
            path = reverse(f'admin:{self.app_label}_template_change', args=[t.pk])
            self._test_system_context_field_helper(path)

        with self.subTest('test field present in vpn add form'):
            path = reverse(f'admin:{self.app_label}_vpn_add')
            self._test_system_context_field_helper(path)

        with self.subTest('test field present in vpn change form'):
            path = reverse(f'admin:{self.app_label}_vpn_change', args=[v.pk])
            self._test_system_context_field_helper(path)

        with self.subTest('test field present in device add form'):
            path = reverse(f'admin:{self.app_label}_device_add')
            self._test_system_context_field_helper(path)

        with self.subTest('test field present in device change form'):
            path = reverse(f'admin:{self.app_label}_device_change', args=[d.pk])
            self._test_system_context_field_helper(path)

    def test_no_system_context(self):
        self._create_template()
        old_context = app_settings.CONTEXT.copy()
        app_settings.CONTEXT = {}
        path = reverse(f'admin:{self.app_label}_template_add')
        r = self.client.get(path)
        self.assertContains(
            r, 'There are no system defined variables available right now'
        )
        app_settings.CONTEXT = old_context

    def test_config_form_old_templates(self):
        config = self._create_config(organization=self._get_org())
        vpn_template = self._create_template(
            name='vpn1-template', type='vpn', vpn=self._create_vpn(), config={}
        )
        config.templates.add(vpn_template)
        group = self._create_device_group()
        config.device.group_id = group.id
        config.device.full_clean()
        config.device.save()
        vpn_client = config.vpnclient_set.first()
        self.assertNotEqual(vpn_client, None)
        params = self._get_device_params(org=self._get_org())
        params.update(
            {
                'config-0-id': str(config.pk),
                'config-0-device': str(config.device_id),
                'config-INITIAL_FORMS': 1,
                'group': str(group.id),
                'context': '{"interval": "60"}',
                'config-0-templates': str(vpn_template.id),
                '_continue': True,
            }
        )
        path = reverse(f'admin:{self.app_label}_device_change', args=[config.device.pk])
        response = self.client.post(path, params, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(vpn_client, config.vpnclient_set.first())

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        devnull.close()


class TestDeviceGroupAdmin(
    CreateDeviceGroupMixin,
    CreateDeviceMixin,
    TestOrganizationMixin,
    TestAdminMixin,
    TestCase,
):
    app_label = 'config'

    def setUp(self):
        self.client.force_login(self._get_admin())

    def test_multitenant_admin(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        user = self._create_org_user(
            organization=org1, is_admin=True, user=self._get_operator()
        ).user
        user.groups.add(Group.objects.get(name='Operator'))

        self._create_device_group(name='Org1 APs', organization=org1)
        self._create_device_group(name='Org2 APs', organization=org2)
        self.client.logout()
        self.client.force_login(user)

        response = self.client.get(
            reverse(f'admin:{self.app_label}_devicegroup_changelist')
        )
        self.assertContains(response, 'Org1 APs')
        self.assertNotContains(response, 'Org2 APs')

    def test_organization_filter(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org1')
        self._create_device_group(name='Org1 APs', organization=org1)
        self._create_device_group(name='Org2 APs', organization=org2)
        url = reverse(f'admin:{self.app_label}_devicegroup_changelist')
        query = f'?organization__id__exact={org1.pk}'
        response = self.client.get(url)
        self.assertContains(response, 'Org1 APs')
        self.assertContains(response, 'Org2 APs')

        response = self.client.get(f'{url}{query}')
        self.assertContains(response, 'Org1 APs')
        self.assertNotContains(response, 'Org2 APs')

    def test_has_devices_filter(self):
        org1 = self._create_org(name='org1')
        dg1 = self._create_device_group(name='Device Group 1', organization=org1)
        self._create_device_group(name='Device Group 2', organization=org1)
        self._create_device(name='d1', group=dg1, organization=org1)
        url = reverse(f'admin:{self.app_label}_devicegroup_changelist') + '?empty='
        response = self.client.get(url + 'true')
        self.assertNotContains(response, 'Device Group 1')
        self.assertContains(response, 'Device Group 2')
        response = self.client.get(url + 'false')
        self.assertContains(response, 'Device Group 1')
        self.assertNotContains(response, 'Device Group 2')

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Device Group, Template
        # and Vpn models
        models = ['devicegroup', 'template', 'vpn']
        self.client.force_login(self._get_admin())
        response = self.client.get(reverse('admin:index'))
        for model in models:
            with self.subTest(f'test menu group link for {model} model'):
                url = reverse(f'admin:{self.app_label}_{model}_changelist')
                self.assertContains(response, f' class="mg-link" href="{url}"')
        with self.subTest('test "Configurations" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Configurations </div>',
                html=True,
            )
        # Test Device is registered as menu item
        with self.subTest('test device menu item is registered'):
            url = reverse(f'admin:{self.app_label}_device_changelist')
            self.assertContains(response, f' class="menu-item" href="{url}"')


class TestDeviceGroupAdminTransaction(
    CreateConfigTemplateMixin,
    CreateDeviceGroupMixin,
    CreateDeviceMixin,
    TestOrganizationMixin,
    TestAdminMixin,
    TransactionTestCase,
):

    app_label = 'config'
    _device_group_params = {
        'name': 'test-device-group',
        'description': 'test device group',
    }
    _additional_params = {}

    def setUp(self):
        self.client.force_login(self._get_admin())

    def _get_device_group_params(self, org, **kwargs):
        p = self._device_group_params.copy()
        p.update(self._additional_params)
        p.update(kwargs)
        p['organization'] = org.pk
        if p.get('templates'):
            p['templates'] = ','.join([str(t.pk) for t in p['templates']])
        return p

    def test_add_devicegroup_does_not_emit_changed_signals(self):
        template = self._create_template()
        org1 = self._get_org()
        path = reverse(f'admin:{self.app_label}_devicegroup_add')
        data = self._get_device_group_params(org=org1, templates=[template])
        self._login()
        with catch_signal(group_templates_changed) as mocked_group_templates_changed:
            self.client.post(path, data)
        mocked_group_templates_changed.assert_not_called()

    def test_templates_not_changed(self):
        template = self._create_template()
        org1 = self._get_org()
        path = reverse(f'admin:{self.app_label}_devicegroup_add')
        data = self._get_device_group_params(org=org1, templates=[template])
        self._login()
        self.client.post(path, data)
        data['name'] = 'templates-not-changed'
        with catch_signal(group_templates_changed) as mocked_group_templates_changed:
            self.client.post(path, data)
        mocked_group_templates_changed.assert_not_called()

    def test_change_devicegroup_templates_emit_changed_signals(self):
        template = self._create_template()
        org = self._get_org()
        dg = self._create_device_group(organization=org)
        path = reverse(f'admin:{self.app_label}_devicegroup_change', args=[dg.pk])
        data = self._get_device_group_params(org=org, templates=[template])
        self._login()
        with catch_signal(group_templates_changed) as mocked_group_templates_changed:
            self.client.post(path, data)
        mocked_group_templates_changed.assert_called_once_with(
            signal=group_templates_changed,
            sender=DeviceGroup,
            instance=dg,
            templates=[template.id],
            old_templates=[],
        )

    def test_group_templates_apply(self):
        t1 = self._create_template(name='t1')
        t2 = self._create_template(name='t2')
        t3 = self._create_template(name='t3', backend='netjsonconfig.OpenWisp')
        org1 = self._get_org()
        dg = self._create_device_group(organization=org1)
        device = self._create_device_config(device_opts=dict(group=dg))
        self._create_device(
            name='test-device-without-config', group=dg, mac_address='00:00:00:00:00:01'
        )
        self.assertEqual(device.config.templates.count(), 0)
        path = reverse(f'admin:{self.app_label}_devicegroup_change', args=[dg.pk])
        self._login()
        with self.subTest('adding templates to group must apply templates to device'):
            data = self._get_device_group_params(org=org1, templates=[t1, t2])
            self.client.post(path, data)
            templates = device.config.templates.all()
            self.assertEqual(templates.count(), 2)
            self.assertIn(t1, templates)
            self.assertIn(t2, templates)

        with self.subTest(
            'removing templates from group must remove templates from device'
        ):
            data = self._get_device_group_params(org=org1, templates=[t2])
            self.client.post(path, data)
            templates = device.config.templates.all()
            self.assertEqual(templates.count(), 1)
            self.assertIn(t2, templates)
            self.assertNotIn(t1, templates)

        with self.subTest(
            'apply templates to device if backend of templates and device are same'
        ):
            data = self._get_device_group_params(org=org1, templates=[t1, t3])
            self.client.post(path, data)
            templates = device.config.templates.all()
            self.assertEqual(templates.count(), 1)
            self.assertNotIn(t3, templates)

    def test_change_device_group_action_changes_templates(self):
        path = reverse(f'admin:{self.app_label}_device_changelist')
        org = self._get_org(org_name='default')
        t1 = self._create_template(name='t1')
        t2 = self._create_template(name='t2')
        dg1 = self._create_device_group(name='test-group-1', organization=org)
        dg1.templates.add(t1)
        dg2 = self._create_device_group(name='test-group-2', organization=org)
        dg2.templates.add(t2)
        device = self._create_device(organization=org, group=dg1)
        templates = device.config.templates.all()
        self.assertNotIn(t2, templates)
        self.assertIn(t1, templates)
        post_data = {
            '_selected_action': [device.pk],
            'action': 'change_group',
            'csrfmiddlewaretoken': 'test',
        }
        with self.subTest('change group'):
            post_data['device_group'] = str(dg2.pk)
            post_data['apply'] = True
            response = self.client.post(path, post_data, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response, 'Successfully changed group of selected devices.'
            )
            templates = device.config.templates.all()
            self.assertIn(t2, templates)
            self.assertNotIn(t1, templates)
        with self.subTest('unassign group'):
            post_data['device_group'] = ''
            response = self.client.post(path, post_data, follow=True)
            self.assertEqual(response.status_code, 200)
            templates = list(device.config.templates.all())
            self.assertEqual(templates, [])

    def test_change_device_group_changes_templates(self):
        org = self._get_org(org_name='default')
        t1 = self._create_template(name='t1')
        t2 = self._create_template(name='t2')
        dg1 = self._create_device_group(name='test-group-1', organization=org)
        dg1.templates.add(t1)
        dg2 = self._create_device_group(name='test-group-2', organization=org)
        dg2.templates.add(t2)
        device = self._create_device(organization=org, group=dg1)
        templates = device.config.templates.all()
        self.assertNotIn(t2, templates)
        self.assertIn(t1, templates)
        with catch_signal(device_group_changed) as device_group_changed_mock:
            device.group = dg2
            device.save(update_fields=['group'])
        device_group_changed_mock.assert_called_with(
            signal=device_group_changed,
            sender=Device,
            instance=device,
            group_id=dg2.id,
            old_group_id=dg1.id,
        )
        templates = device.config.templates.all()
        self.assertNotIn(t1, templates)
        self.assertIn(t2, templates)
