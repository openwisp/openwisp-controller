from django.conf.urls import url


def get_geo_urls(geo_views):
    return [
        url(
            r'^api/v1/device/(?P<pk>[^/]+)/location/$',
            geo_views.device_location,
            name='api_device_location',
        ),
        url(r'^api/v1/device/geojson/$', geo_views.geojson, name='api_geojson',),
        url(
            r'^api/v1/location/(?P<pk>[^/]+)/device/$',
            geo_views.location_device_list,
            name='api_location_device_list',
        ),
    ]
