from django.urls import re_path

from . import consumers as ow_consumer


def get_routes(consumer=ow_consumer):
    UUID_PATTERN = '[a-fA-F0-9]{8}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{4}-?[a-fA-F0-9]{12}'
    return [
        re_path(
            f'^ws/controller/device/(?P<pk>{UUID_PATTERN})/command$',
            consumer.CommandConsumer.as_asgi(),
        )
    ]
