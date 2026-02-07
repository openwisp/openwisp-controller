from django.urls import path, register_converter

from .converters import UUIDAnyConverter, UUIDAnyOrFKConverter
from .views import schema

register_converter(UUIDAnyConverter, "uuid_any")
register_converter(UUIDAnyOrFKConverter, "uuid_or_fk")


register_converter(UUIDAnyConverter, "uuid_any")
register_converter(UUIDAnyOrFKConverter, "uuid_or_fk")

app_name = "openwisp_controller"
urlpatterns = [path("config/schema.json", schema, name="schema")]
