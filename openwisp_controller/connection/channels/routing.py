from django.urls import re_path

from . import consumers as ow_consumer


def get_routes(consumer=ow_consumer):
    return [
        re_path(
            r'^ws/controller/device/(?P<pk>[^/]+)/command$',
            consumer.CommandConsumer.as_asgi(),
        )
    ]
