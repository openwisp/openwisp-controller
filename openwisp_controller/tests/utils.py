from django.contrib.auth import get_user_model
from django.urls import reverse

from openwisp_users.tests.utils import TestMultitenantAdminMixin

user_model = get_user_model()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _test_changelist_recover_deleted(self, app_label, model_label):
        self._test_multitenant_admin(
            url=reverse('admin:{0}_{1}_changelist'.format(app_label, model_label)),
            visible=[],
            hidden=[],
        )

    def _login(self, username='admin', password='tester'):
        self.client.force_login(user_model.objects.get(username=username))
