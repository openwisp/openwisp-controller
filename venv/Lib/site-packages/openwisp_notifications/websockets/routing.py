# chat/routing.py
from django.urls import path

from . import consumers as ow_consumers


def get_routes(consumer=None):
    if not consumer:
        consumer = ow_consumers
    return [
        path("ws/notification/", consumer.NotificationConsumer.as_asgi()),
    ]
