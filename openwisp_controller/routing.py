from openwisp_notifications.websockets.routing import (
    get_routes as get_notification_routes,
)

from openwisp_controller.connection.channels.routing import (
    get_routes as get_connection_routes,
)
from openwisp_controller.geo.channels.routing import get_routes as get_geo_routes


def get_routes():
    return get_geo_routes() + get_connection_routes() + get_notification_routes()
