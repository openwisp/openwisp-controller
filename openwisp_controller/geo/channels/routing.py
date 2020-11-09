from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf.urls import url
from django_loci.channels.base import location_broadcast_path
from openwisp_notifications.websockets.routing import (
    get_routes as get_notification_routes,
)

from .consumers import LocationBroadcast


def get_routes():
    return [url(location_broadcast_path, LocationBroadcast, name='LocationChannel')]


# Kept for backward compatibility
geo_routes = get_routes()

channel_routing = ProtocolTypeRouter(
    {
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(get_notification_routes() + geo_routes)),
        )
    }
)
