from django.conf.urls import url
from django_netjsonconfig.utils import get_api_urls
from openwisp_controller.config.api import views

app_name = 'openwisp_controller'

urlpatterns = [
    url(r'^api/v1/templates/list-create/$',
        views.create_template,
        name='create_template')
] + get_api_urls(views)
