from django.utils.module_loading import import_string

from .settings import CONNECTORS

schema = {}

for connector in CONNECTORS:
    class_path = connector[0]
    class_ = import_string(class_path)
    schema[class_path] = class_.schema
