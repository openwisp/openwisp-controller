from django.urls import path


def get_geo_urls(geo_views):
    return [
        path(
            'api/v1/controller/device/<str:pk>/coordinates/',
            geo_views.device_coordinates,
            name='device_coordinates',
        ),
        path(
            'api/v1/controller/device/<str:pk>/location/',
            geo_views.device_location,
            name='device_location',
        ),
        path(
            'api/v1/controller/location/geojson/',
            geo_views.geojson,
            name='location_geojson',
        ),
        path(
            'api/v1/controller/location/<str:pk>/device/',
            geo_views.location_device_list,
            name='location_device_list',
        ),
        path(
            'api/v1/controller/floorplan/',
            geo_views.list_floorplan,
            name='list_floorplan',
        ),
        path(
            'api/v1/controller/floorplan/<str:pk>/',
            geo_views.detail_floorplan,
            name='detail_floorplan',
        ),
        path(
            'api/v1/controller/location/', geo_views.list_location, name='list_location'
        ),
        path(
            'api/v1/controller/location/<str:pk>/',
            geo_views.detail_location,
            name='detail_location',
        ),
    ]
