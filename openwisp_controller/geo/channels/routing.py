from django_loci.channels.base import location_broadcast_path

from .consumers import LocationBroadcast

channel_routing = [LocationBroadcast.as_route(path=location_broadcast_path)]
