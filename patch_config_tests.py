
class TestReadonlyJsonIssues(TestAdminMixin, TestCase):
    app_label = 'config'

    def setUp(self):
        org = self._get_org()
        self.device = self._create_device(organization=org)
        self.config = self._create_config(device=self.device, config={'test_key': 'test_value'})
        self.template = self._create_template(organization=org, config={'test_key': 'test_value'})
        self.devicegroup = self._create_device_group(organization=org, meta_data={'test_key': 'test_value'})
        self.org_settings = OrganizationConfigSettings.objects.create(organization=org, context={'test_key': 'test_value'})
        
        # operator has read-only access (can view) but cannot change some things depending on permissions
        # let's create a strictly view-only user
        self.view_only_user = self._create_operator()
        self.view_only_user.is_superuser = False
        from django.contrib.auth.models import Permission
        
        # assign view permissions
        for model in ['device', 'config', 'template', 'devicegroup', 'organizationconfigsettings', 'organization']:
            try:
                perm = Permission.objects.get(codename=f'view_{model}')
                self.view_only_user.user_permissions.add(perm)
            except Permission.DoesNotExist:
                pass
        self.view_only_user.save()

    def test_json_rendered_as_html_for_view_only_user(self):
        self.client.force_login(self.view_only_user)
        # Test Template Admin
        path = reverse('%s_%s_change' % ('admin:config', 'template'), args=[self.template.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<pre class="readonly-json">')
        self.assertContains(response, '"test_key"')
        self.assertNotContains(response, "{'test_key': 'test_value'}")

        # Test Device Admin (inlines)
        path = reverse('%s_%s_change' % ('admin:config', 'device'), args=[self.device.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<pre class="readonly-json">')
        self.assertContains(response, '"test_key"')
        self.assertNotContains(response, "{'test_key': 'test_value'}")

        # Test Device Group Admin
        path = reverse('%s_%s_change' % ('admin:config', 'devicegroup'), args=[self.devicegroup.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<pre class="readonly-json">')
        self.assertContains(response, '"test_key"')
        self.assertNotContains(response, "{'test_key': 'test_value'}")
        
    def test_json_editable_for_superuser(self):
        admin = self._get_admin()
        self.client.force_login(admin)
        path = reverse('%s_%s_change' % ('admin:config', 'template'), args=[self.template.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        # It should contain the JSON form widget
        self.assertContains(response, 'djnjc-preformatted')
        
