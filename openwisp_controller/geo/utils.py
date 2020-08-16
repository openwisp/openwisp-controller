from django.conf.urls import url


def get_geo_urls(geo_views):
    return [
        url(
            r'^api/v1/device/(?P<pk>[^/]+)/location/$',
            geo_views.device_location,
            name='api_device_location',
        ),
        url(
            r'^api/device-location/(?P<pk>[^/]+)/$',
            geo_views.device_location,
            name='api_device_location_deprecated',
        ),
    ]
