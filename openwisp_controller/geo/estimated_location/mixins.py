from openwisp_controller.config.whois.service import WHOISService


# These mixins are required as estimated location is an organization level feature.
# Also, adding it this way makes it read-only as well.
class EstimatedLocationMixin:
    """
    Serializer mixin to add estimated location field to the serialized data
    if the estimated location feature is configured and enabled for the organization.
    """

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if WHOISService.check_estimated_location_enabled(obj.organization_id):
            data["is_estimated"] = obj.is_estimated
        else:
            data.pop("is_estimated", None)
        return data


class EstimatedLocationGeoJsonMixin:
    """
    Serializer mixin to add estimated location field to the serialized GeoJSON data
    if the estimated location feature is configured and enabled for the organization.
    """

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if WHOISService.check_estimated_location_enabled(obj.organization_id):
            data["properties"]["is_estimated"] = obj.is_estimated
        else:
            data["properties"].pop("is_estimated", None)
        return data
