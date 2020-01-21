from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf.urls import url
from django_loci.channels.base import location_broadcast_path

from .consumers import LocationBroadcast

channel_routing = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                [url(location_broadcast_path,
                     LocationBroadcast,
                     name='LocationChannel')]
            )
        ),
    )
})
