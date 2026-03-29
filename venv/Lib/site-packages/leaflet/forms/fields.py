from django.contrib.gis.forms.fields import GeometryField as BaseGeometryField

from .widgets import LeafletWidget


class GeometryField(BaseGeometryField):
    widget = LeafletWidget
    geom_type = 'GEOMETRY'

    def __init__(self, *args, csp_nonce=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.geom_type = self.geom_type
        self.widget.csp_nonce = csp_nonce


class GeometryCollectionField(GeometryField):
    geom_type = 'GEOMETRYCOLLECTION'


class PointField(GeometryField):
    geom_type = 'POINT'


class MultiPointField(GeometryField):
    geom_type = 'MULTIPOINT'


class LineStringField(GeometryField):
    geom_type = 'LINESTRING'


class MultiLineStringField(GeometryField):
    geom_type = 'MULTILINESTRING'


class PolygonField(GeometryField):
    geom_type = 'POLYGON'


class MultiPolygonField(GeometryField):
    geom_type = 'MULTIPOLYGON'
