from django.urls import path


def get_command_urls(connection_views):
    return [
        path(
            'api/v1/device/<uuid:device_pk>/command/',
            connection_views.command_list_create_view,
            name='api_device_command_list_create',
        ),
        path(
            'api/v1/device/<uuid:device_pk>/command/<uuid:command_pk>/',
            connection_views.command_details_view,
            name='api_device_command_details',
        ),
    ]
