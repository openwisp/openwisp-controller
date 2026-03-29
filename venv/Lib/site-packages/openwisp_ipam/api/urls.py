from django.urls import path


def get_api_urls(api_views):
    """
    returns:: all the API urls of the app
    arguments::
        api_views: location for getting API views
    """

    return [
        path("import-subnet/", api_views.import_subnet, name="import-subnet"),
        path(
            "subnet/<str:subnet_id>/get-next-available-ip/",
            api_views.get_next_available_ip,
            name="get_next_available_ip",
        ),
        path(
            "subnet/<str:subnet_id>/request-ip/",
            api_views.request_ip,
            name="request_ip",
        ),
        path(
            "subnet/<str:subnet_id>/export/",
            api_views.export_subnet,
            name="export-subnet",
        ),
        path(
            "subnet/<str:subnet_id>/ip-address/",
            api_views.subnet_list_ipaddress,
            name="list_create_ip_address",
        ),
        path("subnet/", api_views.subnet_list_create, name="subnet_list_create"),
        path("subnet/<str:pk>/", api_views.subnet, name="subnet"),
        path("subnet/<str:subnet_id>/hosts/", api_views.subnet_hosts, name="hosts"),
        path("ip-address/<str:pk>/", api_views.ip_address, name="ip_address"),
    ]
