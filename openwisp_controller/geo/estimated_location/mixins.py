from openwisp_controller.config.whois.service import WHOISService


class EstimatedLocationMixin:
    """
    Serializer mixin to add estimated location field to the serialized data
    if the estimated location feature is configured and enabled for the organization.
    """

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if WHOISService.check_estimate_location_configured(obj.organization_id):
            data["is_estimated"] = obj.is_estimated
        else:
            data.pop("is_estimated", None)
        return data


class EstimatedLocationGeoJsonSerializer(EstimatedLocationMixin):
    """
    Extension of EstimatedLocationMixin for GeoJSON serialization.
    """

    def to_representation(self, obj):
        data = super(EstimatedLocationMixin, self).to_representation(obj)
        if WHOISService.check_estimate_location_configured(obj.organization_id):
            data["properties"]["is_estimated"] = obj.is_estimated
        else:
            data["properties"].pop("is_estimated", None)
        return data
