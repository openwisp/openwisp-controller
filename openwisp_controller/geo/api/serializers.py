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

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
DeviceLocation = load_model('geo', 'DeviceLocation')
FloorPlan = load_model('geo', 'FloorPlan')


class LocationDeviceSerializer(ValidatedModelSerializer):
    admin_edit_url = SerializerMethodField('get_admin_edit_url')

    def get_admin_edit_url(self, obj):
        return self.context['request'].build_absolute_uri(
            reverse(f'admin:{obj._meta.app_label}_device_change', args=(obj.id,))
        )

    class Meta:
        model = Device
        fields = '__all__'


class GeoJsonLocationSerializer(gis_serializers.GeoFeatureModelSerializer):
    device_count = IntegerField()

    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = '__all__'


class BaseSerializer(FilterSerializerByOrgManaged, ValidatedModelSerializer):
    pass


class BaseFloorPlanSerializer(BaseSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = FloorPlan
        fields = [
            'id',
            'name',
            'floor',
            'image',
            'created',
            'modified',
        ]
        read_only_fields = [
            'id',
            'created',
            'modified',
        ]

    def get_name(self, obj):
        name = '{0} {1} Floor'.format(obj.location.name, ordinal(obj.floor))
        return name


class FloorPlanSerializer(BaseFloorPlanSerializer, ValidatedModelSerializer):
    class Meta(BaseFloorPlanSerializer.Meta):
        fields = BaseFloorPlanSerializer.Meta.fields + [
            'location',
            'organization',
        ]
        extra_kwargs = {'organization': {'required': False}}

    def validate(self, data):
        if data.get('location'):
            data['organization'] = data.get('location').organization
        return super().validate(data)


class NestedFloorplanSerializer(BaseFloorPlanSerializer):
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
                self.instance = FloorPlan.objects.get(id=data)
                return self.instance
            except (ValidationError, FloorPlan.DoesNotExist):
                raise serializers.ValidationError(
                    detail={
                        'floorplan': _(
                            'FloorPlan object with entered ID does not exists.'
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
            'floor',
            'image',
        )
        extra_kwargs = {'floor': {'required': False}, 'image': {'required': False}}


class DeviceCoordinatesSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = ('name', 'geometry')
        read_only_fields = ('name',)


class LocationSerializer(FilterSerializerByOrgManaged, serializers.ModelSerializer):
    floorplan = FloorPlanLocationSerializer(required=False, allow_null=True)

    class Meta:
        model = Location
        fields = (
            'id',
            'organization',
            'name',
            'type',
            'is_mobile',
            'address',
            'geometry',
            'created',
            'modified',
            'floorplan',
        )
        read_only_fields = ('id', 'created', 'modified')

    def validate(self, data):
        if data.get('type') == 'outdoor' and data.get('floorplan'):
            raise serializers.ValidationError(
                {
                    'type': _(
                        "Floorplan can only be added with location of "
                        "the type indoor"
                    )
                }
            )
        return data

    def to_representation(self, instance):
        request = self.context['request']
        data = super().to_representation(instance)
        floorplans = instance.floorplan_set.all().order_by('-modified')
        floorplan_list = []
        for floorplan in floorplans:
            dict_ = {
                'floor': floorplan.floor,
                'image': request.build_absolute_uri(floorplan.image.url),
            }
            floorplan_list.append(dict_)
        data['floorplan'] = floorplan_list
        return data

    def create(self, validated_data):
        floorplan_data = None

        if validated_data.get('floorplan'):
            floorplan_data = validated_data.pop('floorplan')

        instance = self.instance or self.Meta.model(**validated_data)
        with transaction.atomic():
            instance.full_clean()
            instance.save()

        if floorplan_data:
            floorplan_data['location'] = instance
            floorplan_data['organization'] = instance.organization
            with transaction.atomic():
                fl = FloorPlan.objects.create(**floorplan_data)
                fl.full_clean()
                fl.save()

        return instance

    def update(self, instance, validated_data):
        floorplan_data = None
        if validated_data.get('floorplan'):
            floorplan_data = validated_data.pop('floorplan')

        if floorplan_data:
            floorplan_obj = instance.floorplan_set.order_by('-created').first()
            if floorplan_obj:
                # Update the first floorplan object
                floorplan_obj.floor = floorplan_data.get('floor', floorplan_obj.floor)
                floorplan_obj.image = floorplan_data.get('image', floorplan_obj.image)
                with transaction.atomic():
                    floorplan_obj.full_clean()
                    floorplan_obj.save()
            else:
                if validated_data.get('type') == 'indoor':
                    instance.type = 'indoor'
                    instance.save()
                floorplan_data['location'] = instance
                floorplan_data['organization'] = instance.organization
                fl = FloorPlan.objects.create(**floorplan_data)
                with transaction.atomic():
                    fl.full_clean()
                    fl.save()

        if instance.type == 'indoor' and validated_data.get('type') == 'outdoor':
            floorplans = instance.floorplan_set.all()
            for floorplan in floorplans:
                floorplan.delete()

        return super().update(instance, validated_data)


class NestedtLocationSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = Location
        geo_field = 'geometry'
        fields = (
            'id',
            'type',
            'is_mobile',
            'name',
            'address',
            'geometry',
        )
        read_only_fields = ('id',)

    def get_value(self, dictionary):
        if isinstance(dictionary.get('location'), str):
            return dictionary.get(self.field_name)
        return super().get_value(dictionary)

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                return Location.objects.get(id=data)
            except (ValidationError, Location.DoesNotExist):
                raise serializers.ValidationError(
                    detail={
                        'location': _(
                            'Location object with entered ID does not exists.'
                        )
                    }
                )
        return super().to_internal_value(data)

    def get_attribute(self, instance):
        return instance.location


class DeviceLocationSerializer(serializers.ModelSerializer):
    location = NestedtLocationSerializer()
    floorplan = NestedFloorplanSerializer(required=False, allow_null=True)

    class Meta:
        model = DeviceLocation
        fields = (
            'location',
            'floorplan',
            'indoor',
        )

    @property
    def device_organization_id(self):
        return (
            Device.objects.only('organization_id')
            .get(id=self.context.get('device_id'))
            .organization_id
        )

    def get_or_create_location_object(self, validated_data, location_instance=None):
        location_data = validated_data.pop('location', None)
        if not location_data:
            return
        if isinstance(location_data, dict):
            if 'organization' not in location_data:
                location_data['organization'] = self.device_organization_id
            location_serializer = LocationSerializer(
                data=location_data, instance=location_instance
            )
            location_serializer.is_valid(raise_exception=True)
            return location_serializer.save()
        return location_data

    def get_or_create_floorplan_object(self, validated_data, floorplan_instance=None):
        floorplan_data = validated_data.pop('floorplan', None)
        if not floorplan_data:
            return
        if isinstance(floorplan_data, dict):
            if 'organization' not in floorplan_data:
                floorplan_data['organization'] = self.device_organization_id
            if 'location' not in floorplan_data:
                floorplan_data['location'] = getattr(
                    validated_data['location'], 'id', validated_data['location']
                )
            floorplan_serializer = FloorPlanSerializer(
                data=floorplan_data, instance=floorplan_instance
            )
            try:
                floorplan_serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as error:
                raise serializers.ValidationError(detail={'floorplan': error.detail})
            else:
                return floorplan_serializer.save()
        return floorplan_data

    def _validate(self, data):
        instance = self.instance or self.Meta.model(**data)
        try:
            instance.full_clean()
        except ValidationError as error:
            raise serializers.ValidationError(detail=error.error_dict)
        return data

    def create(self, validated_data):
        validated_data['location'] = self.get_or_create_location_object(validated_data)
        validated_data['floorplan'] = self.get_or_create_floorplan_object(
            validated_data
        )
        validated_data.update(
            {
                'content_object_id': self.context.get('device_id'),
            }
        )
        validated_data = self._validate(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data['location'] = self.get_or_create_location_object(
            validated_data, instance.location
        )
        validated_data['floorplan'] = self.get_or_create_floorplan_object(
            validated_data, instance.floorplan
        )
        validated_data = self._validate(validated_data)
        return super().update(instance, validated_data)
