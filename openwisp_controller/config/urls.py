from django.conf.urls import url

from . import views

app_name = 'openwisp_controller'

urlpatterns = [
    url(r'^config/get-default-templates/(?P<organization_id>[^/]+)/$',
        views.get_default_templates,
        name='get_default_templates'),
]
