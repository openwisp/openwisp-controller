from django.http import JsonResponse
from django.utils.module_loading import import_string
from geopy.extra.rate_limiter import RateLimiter

from ..settings import (
    DJANGO_LOCI_GEOCODE_API_KEY,
    DJANGO_LOCI_GEOCODE_FAILURE_DELAY,
    DJANGO_LOCI_GEOCODE_RETRIES,
    DJANGO_LOCI_GEOCODER,
)

geocoder = import_string(f"geopy.geocoders.{DJANGO_LOCI_GEOCODER}")
if DJANGO_LOCI_GEOCODER != "GoogleV3":
    geolocator = geocoder(user_agent="django_loci")
else:
    geolocator = geocoder(api_key=DJANGO_LOCI_GEOCODE_API_KEY)  # pragma: nocover
geocode = RateLimiter(
    geolocator.geocode,
    max_retries=DJANGO_LOCI_GEOCODE_RETRIES,
    error_wait_seconds=DJANGO_LOCI_GEOCODE_FAILURE_DELAY,
)
reverse_geocode = RateLimiter(
    geolocator.reverse,
    max_retries=DJANGO_LOCI_GEOCODE_RETRIES,
    error_wait_seconds=DJANGO_LOCI_GEOCODE_FAILURE_DELAY,
)


def geocode_view(request):
    address = request.GET.get("address")
    if address is None:
        return JsonResponse({"error": "Address parameter not defined"}, status=400)
    location = geocode(address)
    if location is None:
        return JsonResponse({"error": "Not found location with given name"}, status=404)
    return JsonResponse({"lat": location.latitude, "lng": location.longitude})


def reverse_geocode_view(request):
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    if not lat or not lng:
        return JsonResponse({"error": "lat or lng parameter not defined"}, status=400)
    location = reverse_geocode((lat, lng))
    if location is None:
        return JsonResponse({"address": ""}, status=404)
    # if multiple locations are returned, use the most relevant result
    location = location[0] if isinstance(location, list) else location
    address = str(location.address)
    return JsonResponse({"address": address})
