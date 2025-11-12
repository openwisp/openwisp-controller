from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from django_loci.channels.base import (
    all_location_boradcast_path,
    location_broadcast_path,
)
from openwisp_notifications.websockets.routing import (
    get_routes as get_notification_routes,
)

from .consumers import AllLocationBroadcast, LocationBroadcast


def get_routes():
    return [
        path(
            location_broadcast_path, LocationBroadcast.as_asgi(), name="LocationChannel"
        ),
        path(
            all_location_boradcast_path,
            AllLocationBroadcast.as_asgi(),
            name="AllLocationChannel",
        ),
    ]


# Kept for backward compatibility
geo_routes = get_routes()

channel_routing = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(get_notification_routes() + geo_routes))
        )
    }
)
