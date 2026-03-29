from leaflet.forms.fields import GeometryField as BaseGeometryField

from .widgets import LeafletWidget


class GeometryField(BaseGeometryField):
    widget = LeafletWidget
