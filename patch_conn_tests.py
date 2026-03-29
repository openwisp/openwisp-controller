
from openwisp_controller.tests.utils import TestAdminMixin
from openwisp_controller.connection.tests.utils import CreateDeviceMixin, CreateCredentialsMixin
from django.test import TestCase
from django.urls import reverse

class TestConnectionReadonlyJsonIssues(TestAdminMixin, CreateDeviceMixin, CreateCredentialsMixin, TestCase):
    app_label = 'connection'

    def setUp(self):
        org = self._get_org()
        self.credentials = self._create_credentials(organization=org, params={'test_cred': 'hidden_val'})
        
        # operator has read-only access (can view) but cannot change some things depending on permissions
        # let's create a strictly view-only user
        self.view_only_user = self._create_operator()
        self.view_only_user.is_superuser = False
        from django.contrib.auth.models import Permission
        
        # assign view permissions
        for model in ['credentials', 'deviceconnection', 'command']:
            try:
                perm = Permission.objects.get(codename=f'view_{model}')
                self.view_only_user.user_permissions.add(perm)
            except Permission.DoesNotExist:
                pass
        self.view_only_user.save()

    def test_json_rendered_as_html_for_view_only_user(self):
        self.client.force_login(self.view_only_user)
        path = reverse('%s_%s_change' % ('admin:connection', 'credentials'), args=[self.credentials.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<pre class="readonly-json">')
        self.assertContains(response, '"test_cred"')
        self.assertNotContains(response, "{'test_cred': 'hidden_val'}")

    def test_shared_credentials_hidden_params_for_non_superuser(self):
        # Create a shared credential (organization=None)
        shared_cred = self._create_credentials(organization=None, params={'secret': 'not_seen'})
        self.client.force_login(self.view_only_user)
        path = reverse('%s_%s_change' % ('admin:connection', 'credentials'), args=[shared_cred.pk])
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        # Should not see params field at all, or it is hidden
        self.assertNotContains(response, '"secret"')

