from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.urls import path

from django_loci.channels.base import (
    common_location_broadcast_path,
    location_broadcast_path,
)
from django_loci.channels.consumers import CommonLocationBroadcast, LocationBroadcast

channel_routing = ProtocolTypeRouter(
    {
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    [
                        path(
                            location_broadcast_path,
                            LocationBroadcast.as_asgi(),
                            name="LocationChannel",
                        ),
                        path(
                            common_location_broadcast_path,
                            CommonLocationBroadcast.as_asgi(),
                            name="AllLocationChannel",
                        ),
                    ]
                )
            )
        ),
        "http": get_asgi_application(),
    }
)
