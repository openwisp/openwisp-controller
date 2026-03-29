from ..models import Location
from .base import BaseCommonLocationBroadcast, BaseLocationBroadcast


class LocationBroadcast(BaseLocationBroadcast):
    model = Location


class CommonLocationBroadcast(BaseCommonLocationBroadcast):
    model = Location
