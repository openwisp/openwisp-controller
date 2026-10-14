from copy import copy

from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.serializers import IntegerField, SerializerMethodField
from rest_framework_gis import serializers as gis_serializers
from swapper import load_model

from openwisp_users.api.mixins import FilterSerializerByOrgManaged
from openwisp_utils.api.serializers import ValidatedModelSerializer

from ...serializers import BaseSerializer
from ..estimated_location.mixins import (
    EstimatedLocationGeoJsonMixin,
    EstimatedLocationMixin,
)

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
FloorPlan = load_model("geo", "FloorPlan")
OrganizationGeoSettings = load_model("geo", "OrganizationGeoSettings")


class OrganizationGeoSettingsSerializer(ValidatedModelSerializer):
    class Meta:
        model = OrganizationGeoSettings
        fields = "__all__"
        read_only_fields = ["organization"]


class LocationDeviceSerializer(ValidatedModelSerializer):
    admin_edit_url = SerializerMethodField("get_admin_edit_url")

    def get_admin_edit_url(self, obj):
        return self.context["request"].build_absolute_uri(
            reverse(f"admin:{obj._meta.app_label}_device_change", args=(obj.id,))
        )

    class Meta:
        model = Device
        exclude = ["key"]


class GeoJsonLocationSerializer(
    EstimatedLocationGeoJsonMixin, gis_serializers.GeoFeatureModelSerializer
):
    device_count = IntegerField()

    class Meta:
        model = Location
        geo_field = "geometry"
        fields = "__all__"


class BaseFloorPlanSerializer(BaseSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = FloorPlan
        fields = [
            "id",
            "name",
            "floor",
            "image",
            "created",
            "modified",
        ]
        read_only_fields = [
            "id",
            "created",
            "modified",
        ]

    def get_name(self, obj):
        name = "{0} {1} Floor".format(obj.location.name, ordinal(obj.floor))
        return name


class FloorPlanSerializer(BaseFloorPlanSerializer, ValidatedModelSerializer):
    class Meta(BaseFloorPlanSerializer.Meta):
        fields = BaseFloorPlanSerializer.Meta.fields + [
            "location",
            "organization",
        ]
        extra_kwargs = {"organization": {"required": False}}

    def validate(self, data):
        if data.get("location"):
            data["organization"] = data.get("location").organization
        return super().validate(data)


class NestedFloorplanSerializer(BaseFloorPlanSerializer):
    queryset = FloorPlan.objects.all()

    class Meta(BaseFloorPlanSerializer.Meta):
        pass

    def validate(self, data):
        # This method has been overridden because this
        # serializer does not handle all fields of FloorPlan
        # model and ValidatedModelSerializer.validate complains
        # for non-handled fields.
        return data

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                self.instance = self.queryset.get(id=data)
                return self.instance
            except (ValidationError, FloorPlan.DoesNotExist):
                raise serializers.ValidationError(
                    detail={
                        "floorplan": _(
                            "FloorPlan object with entered ID does not exists."
                        )
                    }
                )
        return super().to_internal_value(data)

    def get_attribute(self, instance):
        return instance.floorplan


class FloorPlanLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorPlan
        fields = (
            "floor",
            "image",
        )
        extra_kwargs = {"floor": {"required": False}, "image": {"required": False}}


class DeviceCoordinatesSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = "geometry"
        fields = ("name", "geometry")
        read_only_fields = ("name",)


class LocationSerializer(EstimatedLocationMixin, BaseSerializer):
    floorplan = FloorPlanLocationSerializer(required=False, allow_null=True)

    class Meta:
        model = Location
        fields = (
            "id",
            "organization",
            "name",
            "type",
            "is_mobile",
            "address",
            "geometry",
            "created",
            "modified",
            "floorplan",
        )
        read_only_fields = ("id", "created", "modified")

    def validate(self, data):
        if data.get("type") == "outdoor" and data.get("floorplan"):
            raise serializers.ValidationError(
                {
                    "type": _(
                        "Floorplan can only be added with location of the type indoor"
                    )
                }
            )
        return data

    def to_representation(self, instance):
        request = self.context["request"]
        data = super().to_representation(instance)
        # floorplan_set is already prefetched and ordered in the view
        floorplans = instance.floorplan_set.all()
        floorplan_list = []
        for floorplan in floorplans:
            dict_ = {
                "floor": floorplan.floor,
                "image": request.build_absolute_uri(floorplan.image.url),
            }
            floorplan_list.append(dict_)
        data["floorplan"] = floorplan_list
        return data

    def create(self, validated_data):
        floorplan_data = None

        if validated_data.get("floorplan"):
            floorplan_data = validated_data.pop("floorplan")

        instance = self.instance or self.Meta.model(**validated_data)
        with transaction.atomic():
            instance.full_clean()
            instance.save()

        if floorplan_data:
            floorplan_data["location"] = instance
            floorplan_data["organization"] = instance.organization
            with transaction.atomic():
                fl = FloorPlan.objects.create(**floorplan_data)
                fl.full_clean()
                fl.save()

        return instance

    def update(self, instance, validated_data):
        floorplan_data = None
        if validated_data.get("floorplan"):
            floorplan_data = validated_data.pop("floorplan")

        if floorplan_data:
            floorplan_obj = instance.floorplan_set.order_by("-created").first()
            if floorplan_obj:
                # Update the first floorplan object
                floorplan_obj.floor = floorplan_data.get("floor", floorplan_obj.floor)
                floorplan_obj.image = floorplan_data.get("image", floorplan_obj.image)
                with transaction.atomic():
                    floorplan_obj.full_clean()
                    floorplan_obj.save()
            else:
                if validated_data.get("type") == "indoor":
                    instance.type = "indoor"
                    instance.save()
                floorplan_data["location"] = instance
                floorplan_data["organization"] = instance.organization
                fl = FloorPlan.objects.create(**floorplan_data)
                with transaction.atomic():
                    fl.full_clean()
                    fl.save()

        if instance.type == "indoor" and validated_data.get("type") == "outdoor":
            floorplans = instance.floorplan_set.all()
            for floorplan in floorplans:
                floorplan.delete()

        return super().update(instance, validated_data)


class NestedtLocationSerializer(
    EstimatedLocationGeoJsonMixin, gis_serializers.GeoFeatureModelSerializer
):
    queryset = Location.objects.all()

    class Meta:
        model = Location
        geo_field = "geometry"
        fields = (
            "id",
            "type",
            "is_mobile",
            "name",
            "address",
            "geometry",
        )
        read_only_fields = ("id",)

    def get_value(self, dictionary):
        if isinstance(dictionary.get("location"), str):
            return dictionary.get(self.field_name)
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                return self.queryset.get(id=data)
            except (ValidationError, Location.DoesNotExist):
                raise serializers.ValidationError(
                    detail={
                        "location": _(
                            "Location object with entered ID does not exists."
                        )
                    }
                )
        return super().to_internal_value(data)

    def get_attribute(self, instance):
        return instance.location


class DeviceLocationSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    location = NestedtLocationSerializer()
    floorplan = NestedFloorplanSerializer(required=False, allow_null=True)

    class Meta:
        model = DeviceLocation
        fields = (
            "location",
            "floorplan",
            "indoor",
        )

    def validate(self, data):
        # Nested objects are prepared and validated in create() or update().
        return data

    @property
    def device_organization_id(self):
        return (
            Device.objects.only("organization_id")
            .get(id=self.context.get("device_id"))
            .organization_id
        )

    def get_or_create_location_object(self, validated_data, location_instance=None):
        location_data = validated_data.pop("location", None)
        if not location_data:
            return None, None
        if isinstance(location_data, dict):
            if "organization" not in location_data:
                location_data["organization"] = self.device_organization_id
            location_serializer = LocationSerializer(
                data=location_data, instance=location_instance
            )
            location_serializer.is_valid(raise_exception=True)
            location = copy(location_instance) if location_instance else Location()
            for field, value in location_serializer.validated_data.items():
                setattr(location, field, value)
            return location, location_serializer
        return location_data, None

    def get_or_create_floorplan_object(self, validated_data, floorplan_instance=None):
        floorplan_data = validated_data.pop("floorplan", None)
        if not floorplan_data:
            return None, False
        if isinstance(floorplan_data, dict):
            floorplan = floorplan_instance or FloorPlan()
            for field, value in floorplan_data.items():
                setattr(floorplan, field, value)
            location = validated_data["location"]
            floorplan.location = location
            if location:
                floorplan.organization_id = location.organization_id
            else:
                floorplan.organization_id = self.device_organization_id
            exclude = []
            if location and location._state.adding:
                exclude.append("location")
            try:
                floorplan.full_clean(exclude=exclude)
            except ValidationError as error:
                raise serializers.ValidationError(
                    detail={"floorplan": error.message_dict}
                )
            return floorplan, True
        return floorplan_data, False

    def _validate(self, data):
        exclude = [
            field
            for field in ["location", "floorplan"]
            if getattr(data[field], "_state", None) and data[field]._state.adding
        ]
        exclude_validation = self.exclude_validation
        self.exclude_validation = exclude
        try:
            return super().validate(data)
        finally:
            self.exclude_validation = exclude_validation

    def _save_related_objects(
        self, validated_data, location_serializer, save_floorplan
    ):
        if location_serializer:
            validated_data["location"] = location_serializer.save()
        if save_floorplan:
            validated_data["floorplan"].location = validated_data["location"]
            validated_data["floorplan"].save()

    def create(self, validated_data):
        validated_data["location"], location_serializer = (
            self.get_or_create_location_object(validated_data)
        )
        validated_data["floorplan"], save_floorplan = (
            self.get_or_create_floorplan_object(validated_data)
        )
        validated_data.update(
            {
                "content_object_id": self.context.get("device_id"),
            }
        )
        validated_data = self._validate(validated_data)
        self._save_related_objects(validated_data, location_serializer, save_floorplan)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.setdefault("location", instance.location)
        validated_data.setdefault("floorplan", instance.floorplan)
        validated_data["location"] = self.get_or_create_location_object(
            validated_data, instance.location
        )
        validated_data["floorplan"], save_floorplan = (
            self.get_or_create_floorplan_object(validated_data, instance.floorplan)
        )
        validated_data = self._validate(validated_data)
        self._save_related_objects(validated_data, location_serializer, save_floorplan)
        return super().update(instance, validated_data)


class IndoorCoordinatesSerializer(serializers.ModelSerializer):
    admin_edit_url = SerializerMethodField("get_admin_edit_url")
    device_id = serializers.UUIDField(source="content_object.id", read_only=True)
    floorplan_id = serializers.UUIDField(source="floorplan.id", read_only=True)
    device_name = serializers.CharField(source="content_object.name")
    mac_address = serializers.CharField(source="content_object.mac_address")
    floor_name = serializers.SerializerMethodField()
    floor = serializers.IntegerField(source="floorplan.floor")
    image = serializers.ImageField(source="floorplan.image", read_only=True)
    coordinates = serializers.SerializerMethodField()

    class Meta:
        model = DeviceLocation
        fields = [
            "id",
            "admin_edit_url",
            "device_id",
            "floorplan_id",
            "device_name",
            "mac_address",
            "floor_name",
            "floor",
            "image",
            "coordinates",
        ]

    def get_admin_edit_url(self, obj):
        return self.context["request"].build_absolute_uri(
            reverse(
                f"admin:{obj.content_object._meta.app_label}_device_change",
                args=(obj.content_object.id,),
            )
        )

    def get_floor_name(self, obj):
        if not obj.floorplan:
            return None
        return str(obj.floorplan)

    def get_coordinates(self, obj):
        """
        NetJsonGraph expects indoor coordinates in {'lat': y, 'lng': x}.
        """
        if not obj.indoor:
            return None
        try:
            y, x = (v.strip() for v in obj.indoor.split(",", 1))
            return {"lat": float(y), "lng": float(x)}
        except (ValueError, TypeError):
            return None
