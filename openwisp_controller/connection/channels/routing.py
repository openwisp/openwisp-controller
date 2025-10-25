from django.urls import re_path

from . import consumers as ow_consumer

uuid_regex = (
    r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}"
)


def get_routes(consumer=ow_consumer):
    return [
        re_path(
            rf"^ws/controller/device/(?P<pk>{uuid_regex})/command$",
            consumer.CommandConsumer.as_asgi(),
        )
    ]
