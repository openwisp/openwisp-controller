import logging

from django import forms
from leaflet.admin import LeafletAdminWidget as BaseLeafletWidget

logger = logging.getLogger(__name__)


class ImageWidget(forms.FileInput):
    """
    Image widget which can show a thumbnail
    and carries information regarding
    the image width and height
    """

    template_name = "admin/widgets/image.html"

    def __init__(self, *args, **kwargs):
        self.thumbnail = kwargs.pop("thumbnail", True)
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        c = super().get_context(name, value, attrs)
        if value and hasattr(value, "url"):
            c.update(
                {"filename": value.name, "url": value.url, "thumbnail": self.thumbnail}
            )
            try:
                c.update({"width": value.width, "height": value.height})
            except IOError:
                msg = "floorplan image not found while showing floorplan:\n{0}"
                logger.error(msg.format(value.name))
        return c


class FloorPlanWidget(forms.TextInput):
    """
    widget that allows to manage indoor coordinates
    """

    template_name = "admin/widgets/floorplan.html"


class LeafletWidget(BaseLeafletWidget):
    include_media = True
    geom_type = "GEOMETRY"
    template_name = "leaflet/admin/widget.html"
    modifiable = True
    display_raw = False
    settings_overrides = {}
