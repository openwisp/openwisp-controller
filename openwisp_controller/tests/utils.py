from django.contrib.auth import get_user_model

from openwisp_users.tests.utils import TestMultitenantAdminMixin

user_model = get_user_model()


class TestAdminMixin(TestMultitenantAdminMixin):
    def _login(self, username='admin', password='tester'):
        self.client.force_login(user_model.objects.get(username=username))
