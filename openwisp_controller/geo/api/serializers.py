import io

from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.files.uploadedfile import InMemoryUploadedFile
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


class FloorPlanSerializer(BaseSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = FloorPlan
        fields = (
            'id',
            'name',
            'floor',
            'image',
            'location',
            'created',
            'modified',
        )
        read_only_fields = ('created', 'modified')

    def get_name(self, obj):
        name = '{0} {1} Floor'.format(obj.location.name, ordinal(obj.floor))
        return name

    def validate(self, data):
        if data.get('location'):
            data['organization'] = data.get('location').organization
        instance = self.instance or self.Meta.model(**data)
        instance.full_clean()
        return data


class FloorPlanLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorPlan
        fields = (
            'floor',
            'image',
        )
        extra_kwargs = {'floor': {'required': False}, 'image': {'required': False}}


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
        read_only_fields = ('created', 'modified')

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
            'type',
            'is_mobile',
            'name',
            'address',
            'geometry',
        )


class NestedFloorplanSerializer(serializers.ModelSerializer):
    class Meta:
        model = FloorPlan
        fields = (
            'floor',
            'image',
        )


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

    def to_internal_value(self, value):
        if value.get('location.type') == 'outdoor' and not self.instance.floorplan:
            value._mutable = True
            value.pop('floorplan.floor')
            value.pop('floorplan.image')
            value.pop('indoor')
            value._mutable = False

        if value.get('floorplan'):
            if value.get('floorplan').get('image'):
                if type(value.get('floorplan').get('image')) is str:
                    _image = self.instance.floorplan.image
                    io_image = io.BytesIO(_image.read())
                    image = InMemoryUploadedFile(
                        file=io_image,
                        name=_image.name,
                        field_name='floorplan.image',
                        content_type='image/jpeg',
                        size=_image.size,
                        charset=None,
                    )
                    value['floorplan']['image'] = image
        value = super().to_internal_value(value)
        return value

    def update(self, instance, validated_data):
        if 'location' in validated_data:
            location_data = validated_data.pop('location')
            location = instance.location
            if location.type == 'indoor' and location_data.get('type') == 'outdoor':
                instance.floorplan = None
                validated_data['indoor'] = ""
                location.type = location_data.get('type', location.type)
            location.is_mobile = location_data.get('is_mobile', location.is_mobile)
            location.name = location_data.get('name', location.name)
            location.address = location_data.get('address', location.address)
            location.geometry = location_data.get('geometry', location.geometry)
            location.save()

        if 'floorplan' in validated_data:
            floorplan_data = validated_data.pop('floorplan')
            if instance.location.type == 'indoor':
                if instance.floorplan:
                    floorplan = instance.floorplan
                    floorplan.floor = floorplan_data.get('floor', floorplan.floor)
                    floorplan.image = floorplan_data.get('image', floorplan.image)
                    floorplan.full_clean()
                    floorplan.save()
            if (
                instance.location.type == 'outdoor'
                and location_data['type'] == 'indoor'
            ):
                fl = FloorPlan.objects.create(
                    floor=floorplan_data['floor'],
                    organization=instance.content_object.organization,
                    image=floorplan_data['image'],
                    location=instance.location,
                )
                instance.location.type = 'indoor'
                instance.location.full_clean()
                instance.location.save()
                instance.floorplan = fl

        return super().update(instance, validated_data)
