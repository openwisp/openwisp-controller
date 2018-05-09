import json

from django.test import TestCase
from django.urls import reverse

from openwisp_users.tests.utils import TestOrganizationMixin

from . import CreateConfigTemplateMixin, TestVpnX509Mixin
from ...pki.models import Ca, Cert
from ...tests.utils import TestAdminMixin
from ..models import Config, Device, Template, Vpn


class TestAdmin(CreateConfigTemplateMixin, TestAdminMixin,
                TestVpnX509Mixin, TestOrganizationMixin, TestCase):
    ca_model = Ca
    cert_model = Cert
    config_model = Config
    device_model = Device
    template_model = Template
    vpn_model = Vpn
    operator_permission_filters = [
        {'codename__endswith': 'config'},
        {'codename__endswith': 'device'},
        {'codename__endswith': 'template'},
        {'codename__endswith': 'vpn'},
    ]
    _device_params = {
        'name': 'test-device',
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
        'config-TOTAL_FORMS': 1,
        'config-INITIAL_FORMS': 0,
        'config-MIN_NUM_FORMS': 0,
        'config-MAX_NUM_FORMS': 1,
        # openwisp_controller.connection
        'deviceconnection_set-TOTAL_FORMS': 0,
        'deviceconnection_set-INITIAL_FORMS': 0,
        'deviceconnection_set-MIN_NUM_FORMS': 0,
        'deviceconnection_set-MAX_NUM_FORMS': 1000,
        'deviceip_set-TOTAL_FORMS': 0,
        'deviceip_set-INITIAL_FORMS': 0,
        'deviceip_set-MIN_NUM_FORMS': 0,
        'deviceip_set-MAX_NUM_FORMS': 1000,
    }
    # WARNING - WATCHOUT
    # this class attribute is changed dinamically
    # by other apps which add inlines to DeviceAdmin
    _additional_params = {}

    def _get_device_params(self, org):
        p = self._device_params.copy()
        p.update(self._additional_params)
        p['organization'] = org.pk
        return p

    def test_device_and_template_different_organization(self):
        org1 = self._create_org()
        template = self._create_template(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        config = self._create_config(organization=org2)
        path = reverse('admin:config_device_change', args=[config.device.pk])
        # ensure it fails with error
        self._login()
        params = self._get_device_params(org=org2)
        params.update({
            'config-0-id': config.pk,
            'config-0-device': config.device.pk,
            'config-0-templates': template.pk,
            'config-INITIAL_FORMS': 1,
        })
        response = self.client.post(path, params)
        self.assertContains(response, 'errors field-templates')
        # remove conflicting template and ensure doesn't error
        params.update({'config-0-templates': ''})
        response = self.client.post(path, params)
        self.assertNotContains(response, 'errors field-templates', status_code=302)

    def test_add_device(self):
        org1 = self._create_org()
        t1 = self._create_template(name='t1', organization=org1)
        t2 = self._create_template(name='t2', organization=None)
        path = reverse('admin:config_device_add')
        data = self._get_device_params(org=org1)
        data.update({
            'name': 'testadd',
            'config-0-templates': ','.join([str(t1.pk), str(t2.pk)]),
        })
        self._login()
        self.client.post(path, data)
        queryset = Device.objects.filter(name='testadd')
        self.assertEqual(queryset.count(), 1)
        device = queryset.first()
        self.assertEqual(device.config.templates.count(), 2)
        self.assertEqual(device.config.templates.filter(name__in=['t1', 't2']).count(), 2)

    def test_preview_device(self):
        org = self._create_org()
        self._create_template(organization=org)
        templates = Template.objects.all()
        path = reverse('admin:config_device_preview')
        config = json.dumps({
            'interfaces': [
                {
                    'name': 'eth0',
                    'type': 'ethernet',
                    'addresses': [
                        {
                            'family': 'ipv4',
                            'proto': 'dhcp'
                        }
                    ]
                }
            ]
        })
        data = {
            'name': 'test-device',
            'organization': org.pk,
            'mac_address': self.TEST_MAC_ADDRESS,
            'backend': 'netjsonconfig.OpenWrt',
            'config': config,
            'csrfmiddlewaretoken': 'test',
            'templates': ','.join([str(t.pk) for t in templates])
        }
        self._login()
        response = self.client.post(path, data)
        self.assertContains(response, '<pre class="djnjc-preformatted')
        self.assertContains(response, 'eth0')
        self.assertContains(response, 'dhcp')

    def test_device_preview_button(self):
        config = self._create_config(organization=self._create_org())
        path = reverse('admin:config_device_change', args=[config.device.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def test_template_preview_button(self):
        t = self._create_template(organization=self._create_org())
        path = reverse('admin:config_template_change', args=[t.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def test_vpn_preview_button(self):
        v = self._create_vpn(organization=self._create_org())
        path = reverse('admin:config_vpn_change', args=[v.pk])
        self._login()
        response = self.client.get(path)
        self.assertIn('Preview', str(response.content))

    def _create_multitenancy_test_env(self, vpn=False):
        org1 = self._create_org(name='test1org')
        org2 = self._create_org(name='test2org')
        inactive = self._create_org(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        t1 = self._create_template(name='template1org', organization=org1)
        t2 = self._create_template(name='template2org', organization=org2)
        t3 = self._create_template(name='t3-inactive', organization=inactive)
        d1 = self._create_device(name='org1-config', organization=org1)
        c1 = self._create_config(device=d1, organization=org1)
        d2 = self._create_device(name='org2-config',
                                 organization=org2,
                                 key='ke1',
                                 mac_address='00:11:22:33:44:56')
        c2 = self._create_config(device=d2, organization=org2)
        d3 = self._create_device(name='config-inactive',
                                 organization=inactive,
                                 key='key2',
                                 mac_address='00:11:22:33:44:57')
        c3 = self._create_config(device=d3, organization=inactive)
        c1.templates.add(t1)
        c2.templates.add(t2)
        data = dict(c1=c1, c2=c2, c3_inactive=c3,
                    t1=t1, t2=t2, t3_inactive=t3,
                    org1=org1, org2=org2,
                    inactive=inactive,
                    operator=operator)
        if vpn:
            v1 = self._create_vpn(name='vpn1org', organization=org1)
            v2 = self._create_vpn(name='vpn2org', organization=org2)
            v3 = self._create_vpn(name='vpn3shared', organization=None)
            v4 = self._create_vpn(name='vpn4inactive', organization=inactive)
            t4 = self._create_template(name='vpn-template1org',
                                       organization=org1,
                                       type='vpn',
                                       vpn=v1)
            data.update(dict(vpn1=v1, vpn2=v2,
                             vpn_shared=v3,
                             vpn_inactive=v4,
                             t1_vpn=t4))
        return data

    def test_device_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_device_changelist'),
            visible=[data['c1'].name, data['org1'].name],
            hidden=[data['c2'].name, data['org2'].name,
                    data['c3_inactive'].name]
        )

    def test_device_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_device_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_device_templates_m2m_queryset(self):
        data = self._create_multitenancy_test_env()
        t_shared = self._create_template(name='t-shared',
                                         organization=None)
        self._test_multitenant_admin(
            url=reverse('admin:config_device_add'),
            visible=[str(data['t1']), str(t_shared)],
            hidden=[str(data['t2']), str(data['t3_inactive'])],
        )

    def test_template_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_template_changelist'),
            visible=[data['t1'].name, data['org1'].name],
            hidden=[data['t2'].name, data['org2'].name,
                    data['t3_inactive'].name],
        )

    def test_template_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_template_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_template_vpn_fk_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse('admin:config_template_add'),
            visible=[data['vpn1'].name, data['vpn_shared'].name],
            hidden=[data['vpn2'].name, data['vpn_inactive'].name],
            select_widget=True
        )

    def test_vpn_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse('admin:config_vpn_changelist'),
            visible=[data['org1'].name, data['vpn1'].name],
            hidden=[data['org2'].name, data['inactive'],
                    data['vpn2'].name, data['vpn_shared'].name,
                    data['vpn_inactive'].name]
        )

    def test_vpn_organization_fk_queryset(self):
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse('admin:config_vpn_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True
        )

    def test_vpn_ca_fk_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse('admin:config_vpn_add'),
            visible=[data['vpn1'].ca.name, data['vpn_shared'].ca.name],
            hidden=[data['vpn2'].ca.name, data['vpn_inactive'].ca.name],
            select_widget=True
        )

    def test_vpn_cert_fk_queryset(self):
        data = self._create_multitenancy_test_env(vpn=True)
        self._test_multitenant_admin(
            url=reverse('admin:config_vpn_add'),
            visible=[data['vpn1'].cert.name, data['vpn_shared'].cert.name],
            hidden=[data['vpn2'].cert.name, data['vpn_inactive'].cert.name],
            select_widget=True
        )

    def test_changelist_recover_deleted_button(self):
        self._create_multitenancy_test_env()
        self._test_changelist_recover_deleted('config', 'device')
        self._test_changelist_recover_deleted('config', 'template')
        self._test_changelist_recover_deleted('config', 'vpn')

    def test_recoverlist_operator_403(self):
        self._create_multitenancy_test_env()
        self._test_recoverlist_operator_403('config', 'device')
        self._test_recoverlist_operator_403('config', 'template')
        self._test_recoverlist_operator_403('config', 'vpn')

    def test_device_template_filter(self):
        data = self._create_multitenancy_test_env()
        t_special = self._create_template(name='special', organization=data['org1'])
        self._test_multitenant_admin(
            url=reverse('admin:config_device_changelist'),
            visible=[data['t1'].name, t_special.name],
            hidden=[data['t2'].name, data['t3_inactive'].name]
        )

    def test_device_contains_default_templates_js(self):
        config = self._create_config(organization=self._create_org())
        path = reverse('admin:config_device_change', args=[config.device.pk])
        self._login()
        response = self.client.get(path)
        self.assertContains(response, '// enable default templates')

    def test_template_not_contains_default_templates_js(self):
        template = self._create_template()
        path = reverse('admin:config_template_change', args=[template.pk])
        self._login()
        response = self.client.get(path)
        self.assertNotContains(response, '// enable default templates')

    def test_vpn_not_contains_default_templates_js(self):
        vpn = self._create_vpn()
        path = reverse('admin:config_vpn_change', args=[vpn.pk])
        self._login()
        response = self.client.get(path)
        self.assertNotContains(response, '// enable default templates')
