from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from django_loci.channels.base import location_broadcast_path
from openwisp_notifications.websockets.routing import (
    get_routes as get_notification_routes,
)

from .consumers import LocationBroadcast


def get_routes():
    return [
        path(
            location_broadcast_path, LocationBroadcast.as_asgi(), name='LocationChannel'
        )
    ]


# Kept for backward compatibility
geo_routes = get_routes()

channel_routing = ProtocolTypeRouter(
    {
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(get_notification_routes() + geo_routes))
        )
    }
)
