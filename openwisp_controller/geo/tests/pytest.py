import asyncio
import os
from contextlib import suppress
from unittest import skipIf

import pytest
from channels.db import database_sync_to_async
from channels.routing import ProtocolTypeRouter
from django.conf import settings
from django.contrib.auth import get_permission_codename, get_user_model
from django.contrib.auth.models import Permission
from django.utils.module_loading import import_string
from django_loci.tests import TestChannelsMixin
from swapper import load_model

from openwisp_controller.geo.channels.consumers import (
    CommonLocationBroadcast,
    LocationBroadcast,
)
from openwisp_users.tests.utils import TestOrganizationMixin

from .utils import TestGeoMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
DeviceLocation = load_model("geo", "DeviceLocation")
User = get_user_model()
OrganizationUser = load_model("openwisp_users", "OrganizationUser")
Group = load_model("openwisp_users", "Group")


@skipIf(os.environ.get("SAMPLE_APP", False), "Running tests on SAMPLE_APP")
class TestChannels(TestGeoMixin, TestChannelsMixin, TestOrganizationMixin):
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
        user = await database_sync_to_async(self._create_user)(is_staff=True)
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
        administrator = await Group.objects.acreate(name="Administrator")
        perm = await Permission.objects.filter(
            codename=get_permission_codename("change", self.location_model._meta),
        ).afirst()
        await administrator.permissions.aadd(perm)
        org1 = await database_sync_to_async(self._get_org)(org_name="test1")
        org2 = await database_sync_to_async(self._get_org)(org_name="test2")
        org1_location = await database_sync_to_async(self._create_location)(
            is_mobile=True, organization=org1
        )
        org2_location = await database_sync_to_async(self._create_location)(
            is_mobile=True, organization=org2
        )
        org1_user = await database_sync_to_async(self._create_administrator)(
            organizations=[org1],
            username="user1",
            password="password",
            email="user1@test.org",
        )
        org2_user = await database_sync_to_async(self._create_administrator)(
            organizations=[org2],
            username="user2",
            password="password",
            email="user2@test.org",
        )
        admin = await database_sync_to_async(self._get_admin)()
        org1_communicator = self._get_common_location_communicator(
            await self._get_common_location_request_dict(
                pk=org1_location.pk, user=org1_user
            ),
            org1_user,
        )
        org2_communicator = self._get_common_location_communicator(
            await self._get_common_location_request_dict(
                pk=org2_location.pk, user=org2_user
            ),
            org2_user,
        )
        admin_communicator = self._get_common_location_communicator(
            await self._get_common_location_request_dict(
                pk=org1_location.pk, user=admin
            ),
            admin,
        )
        connected, _ = await org1_communicator.connect()
        assert connected
        connected, _ = await org2_communicator.connect()
        assert connected
        connected, _ = await admin_communicator.connect()
        assert connected

        # Updating co-ordinates for org1_location should notify org1_user and admin,
        await self._save_location(str(org1_location.pk))
        org1_response = await org1_communicator.receive_json_from(timeout=1)
        assert org1_response["id"] == str(org1_location.pk)
        admin_response = await admin_communicator.receive_json_from(timeout=1)
        assert admin_response["id"] == str(org1_location.pk)
        with pytest.raises(asyncio.TimeoutError):
            await org2_communicator.receive_json_from(timeout=1)

        with suppress(asyncio.CancelledError):
            await org2_communicator.disconnect()

        org2_communicator = self._get_common_location_communicator(
            await self._get_common_location_request_dict(
                pk=org2_location.pk, user=org2_user
            ),
            org2_user,
        )
        connected, _ = await org2_communicator.connect()
        assert connected

        # Updating co-ordinates for org2_location should notify org2_user and admin,
        await self._save_location(str(org2_location.pk))
        org2_response = await org2_communicator.receive_json_from(timeout=1)
        assert org2_response["id"] == str(org2_location.pk)
        admin_response = await admin_communicator.receive_json_from(timeout=1)
        assert admin_response["id"] == str(org2_location.pk)
        with pytest.raises(asyncio.TimeoutError):
            await org1_communicator.receive_json_from(timeout=1)

        # The task is been cancelled if not completed in the given timeout
        with suppress(asyncio.CancelledError):
            await org1_communicator.disconnect()
            await org2_communicator.disconnect()
        await admin_communicator.disconnect()

    def test_asgi_application_router(self):
        assert isinstance(self.application, ProtocolTypeRouter)
