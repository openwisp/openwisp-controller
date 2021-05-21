import uuid
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from netjsonconfig import OpenWrt
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin
from openwisp_utils.tests import catch_signal

from .. import settings as app_settings
from ..signals import config_modified, config_status_changed
from ..tasks import logger as task_logger
from ..tasks import update_template_related_config_status
from .utils import CreateConfigTemplateMixin, TestVpnX509Mixin

Config = load_model('config', 'Config')
Device = load_model('config', 'Device')
Template = load_model('config', 'Template')
Vpn = load_model('config', 'Vpn')
Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')
User = get_user_model()

_original_context = app_settings.CONTEXT.copy()


class TestTemplate(
    TestOrganizationMixin, CreateConfigTemplateMixin, TestVpnX509Mixin, TestCase
):
    """
    tests for Template model
    """

    def test_str(self):
        t = Template(name='test', backend='netjsonconfig.OpenWrt')
        self.assertEqual(str(t), 'test')

    def test_backend_class(self):
        t = Template(name='test', backend='netjsonconfig.OpenWrt')
        self.assertIs(t.backend_class, OpenWrt)

    def test_backend_instance(self):
        config = {'general': {'hostname': 'template'}}
        t = Template(name='test', backend='netjsonconfig.OpenWrt', config=config)
        self.assertIsInstance(t.backend_instance, OpenWrt)

    def test_validation(self):
        config = {'interfaces': {'invalid': True}}
        t = Template(name='test', backend='netjsonconfig.OpenWrt', config=config)
        # ensure django ValidationError is raised
        with self.assertRaises(ValidationError):
            t.full_clean()

    def test_config_status_modified_after_template_added(self):
        t = self._create_template()
        c = self._create_config(device=self._create_device(name='test-status'))
        c.status = 'applied'
        c.save()
        c.refresh_from_db()
        with catch_signal(config_status_changed) as handler:
            c.templates.add(t)
            c.refresh_from_db()
            handler.assert_called_once_with(
                sender=Config, signal=config_status_changed, instance=c
            )

    def test_no_auto_hostname(self):
        t = self._create_template()
        self.assertNotIn('general', t.backend_instance.config)
        t.refresh_from_db()
        self.assertNotIn('general', t.config)

    def test_default_template(self):
        # no default templates defined yet
        org = self._get_org()
        c = self._create_config(organization=org)
        self.assertEqual(c.templates.count(), 0)
        c.device.delete()
        # create default templates for different backends
        t1 = self._create_template(
            name='default-openwrt', backend='netjsonconfig.OpenWrt', default=True
        )
        t2 = self._create_template(
            name='default-openwisp', backend='netjsonconfig.OpenWisp', default=True
        )
        c1 = self._create_config(
            device=self._create_device(name='test-openwrt'),
            backend='netjsonconfig.OpenWrt',
        )
        d2 = self._create_device(
            name='test-openwisp', mac_address=self.TEST_MAC_ADDRESS.replace('55', '56')
        )
        c2 = self._create_config(device=d2, backend='netjsonconfig.OpenWisp')
        # ensure OpenWRT device has only the default OpenWRT backend
        self.assertEqual(c1.templates.count(), 1)
        self.assertEqual(c1.templates.first().id, t1.id)
        # ensure OpenWISP device has only the default OpenWISP backend
        self.assertEqual(c2.templates.count(), 1)
        self.assertEqual(c2.templates.first().id, t2.id)

    def test_vpn_missing(self):
        try:
            self._create_template(type='vpn')
        except ValidationError as err:
            self.assertTrue('vpn' in err.message_dict)
        else:
            self.fail('ValidationError not raised')

    def test_generic_has_no_vpn(self):
        t = self._create_template(vpn=self._create_vpn())
        self.assertIsNone(t.vpn)
        self.assertFalse(t.auto_cert)

    def test_generic_has_create_cert_false(self):
        t = self._create_template()
        self.assertFalse(t.auto_cert)

    def test_auto_client_template(self):
        org = self._get_org()
        vpn = self._create_vpn(organization=org)
        t = self._create_template(
            name='autoclient',
            organization=org,
            type='vpn',
            auto_cert=True,
            vpn=vpn,
            config={},
        )
        control = t.vpn.auto_client()
        self.assertDictEqual(t.config, control)

    def test_auto_client_template_auto_cert_False(self):
        vpn = self._create_vpn()
        t = self._create_template(
            name='autoclient', type='vpn', auto_cert=False, vpn=vpn, config={}
        )
        vpn = t.config['openvpn'][0]
        self.assertEqual(vpn['cert'], 'cert.pem')
        self.assertEqual(vpn['key'], 'key.pem')
        self.assertEqual(len(t.config['files']), 1)
        self.assertIn('ca_path', t.config['files'][0]['path'])

    @mock.patch.dict(app_settings.CONTEXT, {'vpnserver1': 'vpn.testdomain.com'})
    def test_template_context_var(self):
        org = self._get_org()
        t = self._create_template(
            organization=org,
            config={
                'files': [
                    {
                        'path': '/etc/vpnserver1',
                        'mode': '0600',
                        'contents': '{{ name }}\n{{ vpnserver1 }}\n',
                    }
                ]
            },
        )
        c = self._create_config(organization=org)
        c.templates.add(t)
        # clear cache
        del c.backend_instance
        output = c.backend_instance.render()
        vpnserver1 = app_settings.CONTEXT['vpnserver1']
        self.assertIn(vpnserver1, output)

    @mock.patch.dict(app_settings.CONTEXT, {'vpnserver1': 'vpn.testdomain.com'})
    def test_get_context(self):
        t = self._create_template()
        expected = {}
        expected.update(app_settings.CONTEXT)
        self.assertEqual(t.get_context(), expected)

    def test_tamplates_clone(self):
        org = self._get_org()
        t = self._create_template(organization=org, default=True)
        t.save()
        user = User.objects.create_superuser(
            username='admin', password='tester', email='admin@admin.com'
        )
        c = t.clone(user)
        c.full_clean()
        c.save()
        self.assertEqual(c.name, '{} (Clone)'.format(t.name))
        self.assertIsNotNone(c.pk)
        self.assertNotEqual(c.pk, t.pk)
        self.assertFalse(c.default)

    def test_duplicate_files_in_template(self):
        try:
            self._create_template(
                name='test-vpn-1',
                config={
                    'files': [
                        {
                            'path': '/etc/vpnserver1',
                            'mode': '0644',
                            'contents': '{{ name }}\n{{ vpnserver1 }}\n',
                        },
                        {
                            'path': '/etc/vpnserver1',
                            'mode': '0644',
                            'contents': '{{ name }}\n{{ vpnserver1 }}\n',
                        },
                    ]
                },
            )
        except ValidationError as e:
            self.assertIn('Invalid configuration triggered by "#/files"', str(e))
        else:
            self.fail('ValidationError not raised!')

    def test_variable_substition(self):
        config = {"dns_servers": ["{{dns}}"]}
        default_values = {"dns": "4.4.4.4"}
        options = {
            "name": "test1",
            "backend": "netjsonconfig.OpenWrt",
            "config": config,
            "default_values": default_values,
        }
        temp = Template(**options)
        temp.full_clean()
        temp.save()
        obj = Template.objects.get(name='test1')
        self.assertEqual(obj.name, 'test1')

    def test_default_value_validation(self):
        options = {
            'name': 'test1',
            'backend': 'netjsonconfig.OpenWrt',
            'config': {'dns_server': '8.8.8.8'},
        }
        template = Template(**options)

        for value in [None, '', False]:
            with self.subTest(f'testing {value} in template.default_values'):
                template.default_values = value
                template.full_clean()
                self.assertEqual(template.default_values, {})

        for value in [['a', 'b'], '"test"']:
            with self.subTest(f'testing {value} in template.default_values'):
                template.default_values = value
                with self.assertRaises(ValidationError) as context_manager:
                    template.full_clean()
                message_dict = context_manager.exception.message_dict
                self.assertIn('default_values', message_dict)
                self.assertIn(
                    'the supplied value is not a JSON object',
                    message_dict['default_values'],
                )

    def test_template_with_org(self):
        org = self._get_org()
        template = self._create_template(organization=org)
        self.assertEqual(template.organization_id, org.pk)

    def test_template_without_org(self):
        template = self._create_template()
        self.assertIsNone(template.organization)

    def test_template_with_shared_vpn(self):
        vpn = self._create_vpn()  # shared VPN
        org = self._get_org()
        template = self._create_template(organization=org, type='vpn', vpn=vpn)
        self.assertIsNone(vpn.organization)
        self.assertEqual(template.vpn_id, vpn.pk)

    def test_template_and_vpn_different_organization(self):
        org1 = self._get_org()
        vpn = self._create_vpn(organization=org1)
        org2 = self._create_org(name='test org2', slug='test-org2')
        try:
            self._create_template(organization=org2, type='vpn', vpn=vpn)
        except ValidationError as e:
            self.assertIn('organization', e.message_dict)
            self.assertIn('related VPN server match', e.message_dict['organization'][0])
        else:
            self.fail('ValidationError not raised')

    def test_org_default_template(self):
        org1 = self._create_org(name='org1')
        org2 = self._create_org(name='org2')
        self._create_template(organization=org1, name='t1', default=True)
        self._create_template(organization=org2, name='t2', default=True)
        d1 = self._create_device(organization=org1, name='d1')
        c1 = self._create_config(device=d1)
        self.assertEqual(c1.templates.count(), 1)
        self.assertEqual(c1.templates.filter(name='t1').count(), 1)
        d2 = self._create_device(
            organization=org2,
            name='d2',
            mac_address='00:00:00:11:22:33',
            key='1234567890',
        )
        c2 = self._create_config(device=d2)
        self.assertEqual(c2.templates.count(), 1)
        self.assertEqual(c2.templates.filter(name='t2').count(), 1)

    def test_org_default_shared_template(self):
        org1 = self._create_org(name='org1')
        self._create_template(organization=org1, name='t1', default=True)
        self._create_template(organization=None, name='t2', default=True)
        c1 = self._create_config(organization=org1)
        self.assertEqual(c1.templates.count(), 2)
        self.assertEqual(c1.templates.filter(name='t1').count(), 1)
        self.assertEqual(c1.templates.filter(name='t2').count(), 1)

    def test_auto_client_template_default(self):
        org = self._get_org()
        vpn = self._create_vpn(organization=org)
        self._create_template(
            name='autoclient',
            organization=org,
            default=True,
            type='vpn',
            auto_cert=True,
            vpn=vpn,
            config={},
        )
        self._create_config(organization=org)

    def test_auto_generated_certificate_for_organization(self):
        organization = self._get_org()
        vpn = self._create_vpn()
        template = self._create_template(type='vpn', auto_cert=True, vpn=vpn)
        corresponding_device = self._create_device(organization=organization)
        config = self._create_config(device=corresponding_device)
        config.templates.add(template)
        vpn_clients = config.vpnclient_set.all()
        for vpn_client in vpn_clients:
            self.assertIsNotNone(vpn_client.cert.organization)
            self.assertEqual(vpn_client.cert.organization, config.device.organization)

    def test_template_name_and_organization_unique(self):
        org = self._get_org()
        self._create_template(name='template', organization=org, default=True)
        kwargs = {
            'name': 'template',  # the name attribute is same as in the template created
            'organization': org,
            'default': True,
        }
        # _create_template should raise an exception as
        # two templates with the same organization can't have the same name
        with self.assertRaises(ValidationError):
            self._create_template(**kwargs)

    def test_context_regression(self):
        self.test_auto_generated_certificate_for_organization()

        with self.subTest('test Template.get_context()'):
            template_qs = Template.objects.filter(type='vpn')
            self.assertEqual(template_qs.count(), 1)
            t = template_qs.first()
            self.assertDictContainsSubset(_original_context, t.get_context())
            self.assertEqual(app_settings.CONTEXT, _original_context)

        with self.subTest(
            'test Device.get_context() interacting with VPN client template'
        ):
            device_qs = Device.objects.all()
            self.assertEqual(device_qs.count(), 1)
            d = device_qs.first()
            orig_context_set = set(_original_context.items())
            context_set = set(d.get_context().items())
            self.assertTrue(orig_context_set.issubset(context_set))
            self.assertEqual(app_settings.CONTEXT, _original_context)

    def test_template_with_no_config(self):
        msg = 'The configuration field cannot be empty'
        with self.assertRaisesMessage(ValidationError, msg):
            self._create_template(config={})

    def test_template_get_system_context(self):
        t = self._create_template(default_values={'test': 'value'})
        system_context = t.get_system_context()
        self.assertNotIn('test', system_context.keys())

    def test_template_name_unique_validation(self):
        org = self._get_org()
        template1 = self._create_template(name='test', organization=org)
        self.assertEqual(template1.name, 'test')
        org2 = self._create_org(name='test org2', slug='test-org2')

        with self.subTest('template of other org can have the same name'):
            try:
                template2 = self._create_template(name='test', organization=org2)
            except Exception as e:
                self.fail(f'Unexpected exception: {e}')
            self.assertEqual(template2.name, 'test')

        with self.subTest('template of shared org cannot have the same name'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_template(name='test', organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)
            self.assertIn(
                'There is already a template of another organization',
                message_dict['name'][0],
            )

        with self.subTest(
            'new template of org cannot have the same name as shared template'
        ):
            shared = self._create_template(name='new', organization=None)
            with self.assertRaises(ValidationError) as context_manager:
                self._create_template(name='new', organization=org2)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)
            self.assertIn(
                'There is already another shared template', message_dict['name'][0]
            )

        with self.subTest('ensure object itself is excluded'):
            try:
                shared.full_clean()
            except Exception as e:
                self.fail(f'Unexpected exception {e}')

        with self.subTest('cannot have two shared templates with same name'):
            with self.assertRaises(ValidationError) as context_manager:
                self._create_template(name='new', organization=None)
            message_dict = context_manager.exception.message_dict
            self.assertIn('name', message_dict)

    def test_required_templates(self):
        dummy_config = {'interfaces': []}
        t4 = self._create_template(name='default4', config=dummy_config, default=True)
        t2 = self._create_template(name='required2', config=dummy_config, required=True)
        t1 = self._create_template(name='required1', config=dummy_config, required=True)
        t3 = self._create_template(name='default3', config=dummy_config, default=True)

        with self.subTest('required makes it also default'):
            self.assertTrue(t1.default)
            t1.default = False
            t1.full_clean()
            self.assertTrue(t1.default)

        with self.subTest('test required templates ordering'):
            config = self._create_config(
                device=self._create_device(name='test-required')
            )
            self.assertTrue(config.templates.filter(pk=t1.pk).exists())
            self.assertTrue(config.templates.filter(pk=t2.pk).exists())
            templates = config.templates.all()
            self.assertEqual(templates[0], t1)
            self.assertEqual(templates[1], t2)
            self.assertEqual(templates[2], t3)
            self.assertEqual(templates[3], t4)

        with self.subTest('removing a required template from a device raises error'):
            with transaction.atomic():
                with self.assertRaises(PermissionDenied) as context:
                    config.templates.remove(t1)
            self.assertIn('Required templates', str(context.exception))

        with self.subTest('clearing required templates is ineffective (sortedm2m)'):
            t5 = self._create_template(name='not-required', required=False)
            config.templates.clear()
            config.templates.add(t5)
            self.assertTrue(config.templates.filter(pk=t1.pk).exists())
            self.assertTrue(config.templates.filter(pk=t2.pk).exists())

        with self.subTest('required template honours backend of config'):
            config.backend = 'netjsonconfig.OpenWisp'
            config.save()
            self.assertEqual(config.templates.count(), 3)

            # This should not raise an exception since backends of
            # t5 and config is not same. Also t5 should not be added back
            config.templates.remove(t1)
            self.assertEqual(config.templates.count(), 2)

            # Similarly, clearing all templates should be possible
            config.templates.clear()
            self.assertEqual(config.templates.count(), 0)

    def test_required_vpn_template_corner_case(self):
        org = self._get_org()
        vpn = self._create_vpn()
        t = self._create_template(
            name='vpn-test',
            type='vpn',
            vpn=vpn,
            auto_cert=True,
            required=True,
            default=True,
        )
        c = self._create_config(organization=org)
        vpn_client = c.vpnclient_set.first()
        self.assertIsNotNone(vpn_client)
        # simulate reordering via sortedm2m
        c.templates.clear()
        c.templates.add(t)
        # ensure no error is raised
        # ValidationError:
        # {'__all__': ['VPN client with this Config and Vpn already exists.']}
        self.assertIsNotNone(vpn_client)


class TestTemplateTransaction(
    TestOrganizationMixin,
    CreateConfigTemplateMixin,
    TestVpnX509Mixin,
    TransactionTestCase,
):
    def test_config_status_modified_after_change(self):
        t = self._create_template()
        c = self._create_config(device=self._create_device(name='test-status'))
        self.assertEqual(c.status, 'modified')

        with self.subTest('signal not sent if related config is in modified status'):
            with catch_signal(config_status_changed) as handler:
                c.templates.add(t)
                handler.assert_not_called()

        c.status = 'applied'
        c.save()
        c.refresh_from_db()
        self.assertEqual(c.status, 'applied')
        t.config['interfaces'][0]['name'] = 'eth1'
        t.full_clean()

        with self.subTest('signal is sent if related config is in applied status'):
            with catch_signal(config_status_changed) as handler:
                t.save()
                c.refresh_from_db()
                handler.assert_called_once_with(
                    sender=Config, signal=config_status_changed, instance=c
                )
                self.assertEqual(c.status, 'modified')

        with self.subTest('signal not sent if config is already modified'):
            # status has already changed to modified
            # sgnal should not be triggered again
            with catch_signal(config_status_changed) as handler:
                t.config['interfaces'][0]['name'] = 'eth2'
                t.full_clean()
                with self.assertNumQueries(8):
                    t.save()
                c.refresh_from_db()
                handler.assert_not_called()
                self.assertEqual(c.status, 'modified')

    def test_config_modified_signal(self):
        conf = self._create_config(device=self._create_device(name='test-status'))
        template1 = self._create_template(name='t1')
        template2 = self._create_template(
            name='t2', organization=conf.device.organization
        )
        self.assertEqual(conf.status, 'modified')
        # refresh instance to reset _just_created attribute
        conf = Config.objects.get(pk=conf.pk)

        with self.subTest('signal sent if config status is already modified'):
            with catch_signal(config_modified) as handler:
                conf.templates.add(template1, template2)
                handler.assert_called_with(
                    sender=Config,
                    signal=config_modified,
                    instance=conf,
                    device=conf.device,
                    config=conf,
                    previous_status='modified',
                    action='m2m_templates_changed',
                )
            self.assertEqual(handler.call_count, 1)

        # reset status
        conf.set_status_applied()

        with self.subTest('signal sent after assigning template to config'):
            with catch_signal(config_modified) as handler:
                conf.templates.remove(template2)
                handler.assert_called_once_with(
                    sender=Config,
                    signal=config_modified,
                    instance=conf,
                    device=conf.device,
                    config=conf,
                    previous_status='applied',
                    action='m2m_templates_changed',
                )
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'modified')

        # reset status
        conf.set_status_applied()

        with self.subTest('post_clear m2m ignored'):
            with catch_signal(config_modified) as handler:
                conf.templates.clear()
                handler.assert_not_called()
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'applied')

        with self.subTest('post_add and previous_status=applied'):
            with catch_signal(config_modified) as handler:
                conf.templates.add(template1, template2)
                handler.assert_called_once_with(
                    sender=Config,
                    signal=config_modified,
                    instance=conf,
                    device=conf.device,
                    config=conf,
                    previous_status='applied',
                    action='m2m_templates_changed',
                )
            self.assertEqual(handler.call_count, 1)
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'modified')

        # reset status
        conf.set_status_applied()

        with self.subTest('test remove/add'):
            with catch_signal(config_modified) as handler:
                conf.templates.remove(template1, template2)
                conf.templates.add(template1, template2)
                self.assertEqual(handler.call_count, 2)
            conf.refresh_from_db()
            self.assertEqual(conf.status, 'modified')

        # reset status
        conf.set_status_applied()

        with self.subTest('signal sent after changing a template'):
            with catch_signal(config_modified) as handler:
                template1.config['interfaces'][0]['name'] = 'eth1'
                template1.full_clean()
                template1.save()
                handler.assert_called_once_with(
                    sender=Config,
                    signal=config_modified,
                    instance=conf,
                    device=conf.device,
                    config=conf,
                    previous_status='applied',
                    action='related_template_changed',
                )
                conf.refresh_from_db()
                self.assertEqual(conf.status, 'modified')

        with self.subTest('signal sent also if config is already in modified status'):
            # status has already changed to modified
            # sgnal should be triggered anyway
            with catch_signal(config_modified) as handler:
                template1.config['interfaces'][0]['name'] = 'eth2'
                template1.full_clean()
                template1.save()
                conf.refresh_from_db()
                handler.assert_called_once_with(
                    sender=Config,
                    signal=config_modified,
                    instance=conf,
                    device=conf.device,
                    config=conf,
                    previous_status='modified',
                    action='related_template_changed',
                )
                self.assertEqual(conf.status, 'modified')

    @mock.patch.object(update_template_related_config_status, 'delay')
    def test_task_called(self, mocked_task):
        with self.subTest('task not called when template is created'):
            template = self._create_template()
            conf = self._create_config(device=self._create_device(name='test-status'))
            conf.set_status_applied()
            mocked_task.assert_not_called()

        with self.subTest('task is called when template conf is changed'):
            template.config['interfaces'][0]['name'] = 'eth1'
            template.full_clean()
            template.save()
            mocked_task.assert_called_with(template.pk)

        mocked_task.reset_mock()

        with self.subTest('task is called when template default_values are changed'):
            template.refresh_from_db()
            template.default_values = {'a': 'a'}
            template.full_clean()
            template.save()
            mocked_task.assert_called_with(template.pk)

        mocked_task.reset_mock()

        with self.subTest('task is not called when there are no changes'):
            template.full_clean()
            template.save()
            mocked_task.assert_not_called()

    @mock.patch.object(task_logger, 'warning')
    def test_task_failure(self, mocked_warning):
        update_template_related_config_status.delay(uuid.uuid4())
        mocked_warning.assert_called_once()

    @mock.patch.object(
        Template, '_update_related_config_status', side_effect=SoftTimeLimitExceeded
    )
    def test_task_timeout(self, mocked_update_related_config_status):
        template = self._create_template()
        with mock.patch.object(task_logger, 'error') as mocked_error:
            template.config['interfaces'][0]['name'] = 'eth2'
            template.full_clean()
            template.save()
            mocked_error.assert_called_once()
        mocked_update_related_config_status.assert_called_once()
