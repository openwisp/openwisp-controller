from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^api/device-location/(?P<pk>[^/]+)/$',
        views.device_location,
        name='api_device_location'),
]
