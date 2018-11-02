from django.conf.urls import url

from . import views

app_name = 'openwisp_controller'

urlpatterns = [
    url(r'^api/device-location/(?P<pk>[^/]+)/$',
        views.device_location,
        name='api_device_location'),
]
