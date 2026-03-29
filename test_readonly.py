import os
import django
from django.conf import settings
from unittest.mock import Mock

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')
django.setup()

from django.contrib.admin import site
from openwisp_controller.config.admin import TemplateAdmin
from openwisp_controller.config.models import Template
from django.contrib.auth.models import User
from django.test import RequestFactory

request = RequestFactory().get('/admin/')
request.user = Mock()
request.user.is_superuser = False
request.user.has_perm = Mock(return_value=False)
request._recover_view = False  

class MockAdmin(TemplateAdmin):
    def has_change_permission(self, request, obj=None):
        return False
    def has_view_permission(self, request, obj=None):
        return True
    def has_add_permission(self, request):
        return False

admin = MockAdmin(Template, site)
obj = Template()

print("fields list:", admin.fields)
print("get_fields:", admin.get_fields(request, obj))
print("get_readonly_fields:", admin.get_readonly_fields(request, obj))
