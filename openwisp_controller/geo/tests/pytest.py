import asyncio
import os
from contextlib import suppress
from unittest import skipIf

import pytest
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import ProtocolTypeRouter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.utils.module_loading import import_string
from django_loci.tests import TestChannelsMixin
from swapper import load_model

from openwisp_controller.geo.channels.consumers import (
    CommonLocationBroadcast,
    LocationBroadcast,
)

from .utils import TestGeoMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
User = get_user_model()
OrganizationUser = load_model("openwisp_users", "OrganizationUser")


@skipIf(os.environ.get("SAMPLE_APP", False), "Running tests on SAMPLE_APP")
class TestChannels(TestGeoMixin, TestChannelsMixin):
    location_consumer = LocationBroadcast
    common_location_consumer = CommonLocationBroadcast
    application = import_string(getattr(settings, "ASGI_APPLICATION"))
    object_model = Device
    location_model = Location
    object_location_model = DeviceLocation
    user_model = get_user_model()

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_consumer_staff_but_no_change_permission(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username="user", password="password", email="test@test.org", is_staff=True
        )
        location = await database_sync_to_async(self._create_location)(is_mobile=True)
        await database_sync_to_async(self._create_object_location)(location=location)
        pk = location.pk
        request_vars = await self._get_specific_location_request_dict(pk=pk, user=user)
        communicator = self._get_specific_location_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add permission to change location and repeat
        perm = await Permission.objects.filter(
            codename=f"change_{self.location_model._meta.model_name}",
            content_type__app_label=self.location_model._meta.app_label,
        ).afirst()
        await database_sync_to_async(user.user_permissions.add)(perm)
        user = await database_sync_to_async(User.objects.get)(pk=user.pk)
        request_vars = await self._get_specific_location_request_dict(pk=pk, user=user)
        communicator = self._get_specific_location_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # add user to organization
        await database_sync_to_async(OrganizationUser.objects.create)(
            organization=location.organization,
            user=user,
            is_admin=True,
        )
        await database_sync_to_async(location.organization.save)()
        user = await database_sync_to_async(User.objects.get)(pk=user.pk)
        request_vars = await self._get_specific_location_request_dict(pk=pk, user=user)
        communicator = self._get_specific_location_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_common_location_consumer_staff_but_no_change_permission(self):
        user = await database_sync_to_async(User.objects.create_user)(
            username="user", password="password", email="test@test.org", is_staff=True
        )
        location = await database_sync_to_async(self._create_location)(is_mobile=True)
        await database_sync_to_async(self._create_object_location)(location=location)
        pk = location.pk
        request_vars = await self._get_common_location_request_dict(pk=pk, user=user)
        communicator = self._get_common_location_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()
        # After granting change permission, the user can connect to the common
        # location endpoint, but must receive updates only for locations
        # belonging to their organization.
        perm = await Permission.objects.filter(
            codename=f"change_{self.location_model._meta.model_name}",
            content_type__app_label=self.location_model._meta.app_label,
        ).afirst()
        await database_sync_to_async(user.user_permissions.add)(perm)
        user = await database_sync_to_async(User.objects.get)(pk=user.pk)
        request_vars = await self._get_common_location_request_dict(pk=pk, user=user)
        communicator = self._get_common_location_communicator(request_vars, user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    @pytest.mark.asyncio
    @pytest.mark.django_db(transaction=True)
    async def test_common_location_org_isolation(self):
        org1 = await database_sync_to_async(self._create_organization)(name="test1")
        org2 = await database_sync_to_async(self._create_organization)(name="test2")
        location1 = await database_sync_to_async(self._create_location)(
            is_mobile=True, organization=org1
        )
        location2 = await database_sync_to_async(self._create_location)(
            is_mobile=True, organization=org2
        )
        user1 = await database_sync_to_async(User.objects.create_user)(
            username="user1", password="password", email="user1@test.org", is_staff=True
        )
        user2 = await database_sync_to_async(User.objects.create_user)(
            username="user2", password="password", email="user2@test.org", is_staff=True
        )
        perm = await Permission.objects.filter(
            codename=f"change_{self.location_model._meta.model_name}",
            content_type__app_label=self.location_model._meta.app_label,
        ).afirst()
        await database_sync_to_async(user1.user_permissions.add)(perm)
        await database_sync_to_async(user2.user_permissions.add)(perm)
        await database_sync_to_async(OrganizationUser.objects.create)(
            organization=org1, user=user1, is_admin=True
        )
        await database_sync_to_async(OrganizationUser.objects.create)(
            organization=org2, user=user2, is_admin=True
        )
        user1 = await database_sync_to_async(User.objects.get)(pk=user1.pk)
        user2 = await database_sync_to_async(User.objects.get)(pk=user2.pk)
        channel_layer = get_channel_layer()
        communicator1 = self._get_common_location_communicator(
            await self._get_common_location_request_dict(pk=location1.pk, user=user1),
            user1,
        )
        communicator2 = self._get_common_location_communicator(
            await self._get_common_location_request_dict(pk=location2.pk, user=user2),
            user2,
        )
        connected, _ = await communicator1.connect()
        assert connected
        connected, _ = await communicator2.connect()
        assert connected
        await channel_layer.group_send(
            f"loci.mobile-location.organization.{org1.pk}",
            {"type": "send.message", "message": {"id": str(location1.pk)}},
        )
        response = await communicator1.receive_json_from(timeout=1)
        assert response["id"] == str(location1.pk)
        with pytest.raises(asyncio.TimeoutError):
            await communicator2.receive_json_from(timeout=1)
        # The task is been cancelled if not completed in the given timeout
        await communicator1.disconnect()
        with suppress(asyncio.CancelledError):
            await communicator2.disconnect()

    def test_asgi_application_router(self):
        assert isinstance(self.application, ProtocolTypeRouter)
