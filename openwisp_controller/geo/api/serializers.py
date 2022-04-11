import uuid

from django.contrib.humanize.templatetags.humanize import ordinal
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import APIException
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
        ]
        read_only_fields = ['id']

    def get_name(self, obj):
        name = '{0} {1} Floor'.format(obj.location.name, ordinal(obj.floor))
        return name


class FloorPlanSerializer(BaseFloorPlanSerializer):
    class Meta(BaseFloorPlanSerializer.Meta):
        fields = BaseFloorPlanSerializer.Meta.fields + ['location','created', 'modified']
        read_only_fields = BaseFloorPlanSerializer.Meta.read_only_fields + ['created', 'modified']


class NestedFloorplanSerializer(BaseFloorPlanSerializer):
    location = None
    class Meta(BaseFloorPlanSerializer.Meta):
        pass

    def is_valid(self, raise_exception=False):
        try:
            return super().is_valid(raise_exception)
        except Exception as e:
            print('>>', e)
            raise e

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                id = uuid.UUID(data)
            except ValueError:
                pass
            else:
                try:
                    self.instance = FloorPlan.objects.get(id=id)
                    return self.instance
                except FloorPlan.DoesNotExist:
                    raise APIException(
                        detail={
                            'floorplan': _(
                                'Floorplan object with entered ID does not exists.'
                            )
                        }
                    )
        return super().to_internal_value(data)

    def run_validators(self, data):
        if isinstance(data, FloorPlan):
            return data
        return super().run_validators(data)

    def get_attribute(self, instance):
        if isinstance(instance, Device):
            return instance.devicelocation.floorplan
        if isinstance(instance, DeviceLocation):
            return instance.floorplan
        super().get_attribute(instance)

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

    def to_internal_value(self, data):
        if isinstance(data, str):
            try:
                id = uuid.UUID(data)
            except ValueError:
                pass
            else:
                try:
                    return Location.objects.get(id=id)
                except Location.DoesNotExist:
                    raise APIException(
                        detail={
                            'location': _(
                                'Location object with entered ID does not exists.'
                            )
                        }
                    )
        return super().to_internal_value(data)

    def get_attribute(self, instance):
        if isinstance(instance, Device):
            return instance.devicelocation.location
        if isinstance(instance, DeviceLocation):
            return instance.location
        super().get_attribute(instance)


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

    def run_validation(self, data):
        view = self.context.get('view')
        device = Device.objects.get(id=view.kwargs.get('pk'))
        if 'location' not in data:
            data['location.organization'] = device.organization_id
        if 'floorplan' not in data:
            data['floorplan.organization'] = device.organization_id
        #     floorplan = {}
        #     for field in self.fields['floorplan'].fields.keys():
        #         floorplan[field] = data.pop(f'floorplan.{field}', None)
        #     data['floorplan'] = floorplan
        from pprint import pprint
        pprint(data)
        return super().run_validation(data)

    def create(self, validated_data):
        print('creating')
        view = self.context.get('view')
        device = Device.objects.get(id=view.kwargs.get('pk'))
        if 'location' in validated_data and isinstance(validated_data['location'], dict):
            location_data = validated_data.pop('location')
            if 'organization' not in location_data:
                location_data['organization'] = device.organization_id
            location_serializer = LocationSerializer(data=location_data)
            try:
                location_serializer.is_valid(raise_exception=True)
            except Exception as e:
                raise e
            location = location_serializer.save()
            validated_data['location'] = location

        if 'floorplan' in validated_data and isinstance(validated_data['floorplan'], dict):
            floorplan_data = validated_data.pop('floorplan')
            if 'location' not in floorplan_data:
                floorplan_data['location'] = validated_data['location']
            print(floorplan_data)
            floorplan_serializer = FloorPlanSerializer(data=floorplan_data)
            try:
                floorplan_serializer.is_valid(raise_exception=True)
            except Exception as e:
                print(e)
                raise e
            floorplan = floorplan_serializer.save()
            validated_data['floorplan'] = floorplan

        validated_data.update(
            {
                'content_object': device,
            }
        )
        return super().create(validated_data)

    # def update(self, instance, validated_data):
    #     if 'location' in validated_data:
    #         location_data = validated_data.pop('location')
    #         location = instance.location
    #         if location.type == 'indoor' and location_data.get('type') == 'outdoor':
    #             instance.floorplan = None
    #             validated_data['indoor'] = ""
    #             location.type = location_data.get('type', location.type)
    #         location.is_mobile = location_data.get('is_mobile', location.is_mobile)
    #         location.name = location_data.get('name', location.name)
    #         location.address = location_data.get('address', location.address)
    #         location.geometry = location_data.get('geometry', location.geometry)
    #         location.save()

    #     if 'floorplan' in validated_data:
    #         floorplan_data = validated_data.pop('floorplan')
    #         if instance.location.type == 'indoor':
    #             if instance.floorplan:
    #                 floorplan = instance.floorplan
    #                 floorplan.floor = floorplan_data.get('floor', floorplan.floor)
    #                 floorplan.image = floorplan_data.get('image', floorplan.image)
    #                 floorplan.full_clean()
    #                 floorplan.save()
    #         if (
    #             instance.location.type == 'outdoor'
    #             and location_data['type'] == 'indoor'
    #         ):
    #             fl = FloorPlan.objects.create(
    #                 floor=floorplan_data['floor'],
    #                 organization=instance.content_object.organization,
    #                 image=floorplan_data['image'],
    #                 location=instance.location,
    #             )
    #             instance.location.type = 'indoor'
    #             instance.location.full_clean()
    #             instance.location.save()
    #             instance.floorplan = fl

    #     return super().update(instance, validated_data)
