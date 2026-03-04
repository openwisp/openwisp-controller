from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django_loci.tests.base.test_admin import BaseTestAdmin
from swapper import load_model

from openwisp_users.tests.utils import TestOrganizationMixin

from ...config.tests.test_admin import TestImportExportMixin
from ...tests.utils import TestAdminMixin
from .utils import TestGeoMixin

Device = load_model("config", "Device")
Location = load_model("geo", "Location")
FloorPlan = load_model("geo", "FloorPlan")
DeviceLocation = load_model("geo", "DeviceLocation")


class TestAdmin(TestAdminMixin, TestGeoMixin, BaseTestAdmin, TestCase):
    app_label = "geo"
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
    user_model = get_user_model()

    def setUp(self):
        """override TestAdminMixin.setUp"""
        pass

    def _create_multitenancy_test_env(self, vpn=False):
        org1 = self._create_organization(name="test1org")
        org2 = self._create_organization(name="test2org")
        inactive = self._create_organization(name="inactive-org", is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        l1 = self._create_location(
            name="location1org", type="indoor", organization=org1
        )
        l2 = self._create_location(
            name="location2org", type="indoor", organization=org2
        )
        l3 = self._create_location(
            name="location-inactive", type="indoor", organization=inactive
        )
        fl1 = self._create_floorplan(location=l1, organization=org1)
        fl2 = self._create_floorplan(location=l2, organization=org2)
        fl3 = self._create_floorplan(location=l3, organization=inactive)
        d1 = self._create_object(
            name="org1-dev",
            organization=org1,
            key="key1",
            mac_address="00:11:22:33:44:56",
        )
        d2 = self._create_object(
            name="org2-dev",
            organization=org2,
            key="key2",
            mac_address="00:12:22:33:44:56",
        )
        d3 = self._create_object(
            name="org3-dev",
            organization=inactive,
            key="key3",
            mac_address="00:13:22:33:44:56",
        )
        self._create_object_location(location=l1, floorplan=fl1, content_object=d1)
        self._create_object_location(location=l2, floorplan=fl2, content_object=d2)
        self._create_object_location(location=l3, floorplan=fl3, content_object=d3)
        data = dict(
            l1=l1,
            l2=l2,
            l3_inactive=l3,
            fl1=fl1,
            fl2=fl2,
            fl3_inactive=fl3,
            org1=org1,
            org2=org2,
            inactive=inactive,
            operator=operator,
        )
        return data

    def test_location_queryset(self):
        self._create_admin()
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_location_changelist"),
            visible=[data["l1"].name, data["org1"].name],
            hidden=[
                data["l2"].name,
                data["org2"].name,
                data["inactive"].name,
                data["l3_inactive"].name,
            ],
        )

    def test_location_organization_fk_autocomplete_view(self):
        self._create_admin()
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=self._get_autocomplete_view_path(
                self.app_label, "location", "organization"
            ),
            visible=[data["org1"].name],
            hidden=[data["org2"].name, data["inactive"]],
        )

    def test_floorplan_queryset(self):
        self._create_admin()
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f"admin:{self.app_label}_floorplan_changelist"),
            visible=[data["fl1"], data["org1"].name],
            hidden=[
                data["fl2"],
                data["org2"].name,
                data["inactive"].name,
                data["fl3_inactive"],
            ],
        )

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Location , FloorPlan

        self.client.force_login(self._create_admin())
        models = ["location", "floorplan"]
        response = self.client.get(reverse("admin:index"))
        for model in models:
            with self.subTest(f"test menu group link for {model} model"):
                url = reverse(f"admin:{self.app_label}_{model}_changelist")
                self.assertContains(response, f' class="mg-link" href="{url}"')
        with self.subTest('test "Geographic Info" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Geographic Info </div>',
                html=True,
            )

    def test_location_readonly_fields(self):
        location = self._create_location(
            name="location1org", type="indoor", organization=self._get_org()
        )
        self._create_admin()
        self._login()
        url = reverse(f"admin:{self.app_label}_location_change", args=[location.pk])
        response = self.client.get(url)
        self.assertNotContains(response, '<input type="checkbox" name="is_estimated"')


class TestDeviceAdmin(
    TestImportExportMixin, TestAdminMixin, TestGeoMixin, TestOrganizationMixin, TestCase
):
    app_label = "config"
    fixtures = ["test_templates"]
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
    user_model = get_user_model()

    resource_fields = TestImportExportMixin.resource_fields[:] + [
        "venue",
        "address",
        "coords",
        "is_mobile",
        "venue_type",
        "floor",
        "floor_position",
        "location_id",
        "floorplan_id",
    ]

    def setUp(self):
        self.client.force_login(self._get_admin())

    def test_device_export_geo(self):
        org = self._get_org(org_name="default")
        location = self._create_location(
            name="location", type="indoor", organization=org
        )
        floorplan = self._create_floorplan(location=location, organization=org)
        device = self._create_object(
            name="test",
            organization=org,
            mac_address="00:11:22:33:44:66",
        )
        self._create_object_location(
            location=location, floorplan=floorplan, content_object=device
        )
        response = self.client.post(
            reverse(f"admin:{self.app_label}_device_export"), {"format": "0"}
        )
        self.assertEqual(response.status_code, 200)
        contents = response.content.decode("utf-8")
        self.assertIn(
            "name,mac_address,organization,group,model,os,system,notes,venue,address,"
            "coords,is_mobile,venue_type,floor,floor_position,last_ip,management_ip,"
            "config_status,config_backend,config_data,config_context,config_templates,"
            "created,modified,id,key,organization_id,group_id,location_id,floorplan_id",
            contents,
        )
        self.assertIn(
            "test,00:11:22:33:44:66,default,,,,,,location,"
            '"Via del Corso, Roma, Italia",POINT (12.512124 41.898903),False,indoor,'
            '1,"-140.38620,40.369227",,,,,,,,',
            contents,
        )
        self.assertIn(
            f"{device.id},{device.key},{org.id},,{location.id},{floorplan.id}",
            contents,
        )

    def test_device_import_geo(self):
        org = self._get_org(org_name="default")
        location = self._create_location(
            name="location1org", type="indoor", organization=org
        )
        floorplan = self._create_floorplan(location=location, organization=org)
        contents = (
            "name,mac_address,organization,group,model,os,system,notes,venue,"
            "address,coords,is_mobile,venue_type,floor,floor_position,last_ip,"
            "management_ip,config_status,config_backend,config_data,config_context"
            ",config_templates,created,modified,id,key,organization_id,group_id,"
            "location_id,floorplan_id\n"
            "test,00:11:22:33:44:66,{org_name},,model,os,system,notes,Test,"
            "Via Test 29,POINT (-57.63463382632019 -25.28397344703963),False,"
            'indoor,-1,"-279.21875,442",127.0.0.1,10.0.0.2,'
            'applied,netjsonconfig.OpenWrt,"{config}","{context}",,'
            "2022-10-17 15:26:51,2022-10-17 15:26:51,"
            "559871c5-ce3d-4c7e-9176-fb6623d562f3,"
            "934d0799b1ce3a454bbb585cda1d7a49,{org_id},"
            ",{location_id},{floorplan_id}"
        ).strip()
        contents = contents.format(
            org_name=org.name,
            org_id=org.id,
            config='{""general"": {}}',
            context='{""ssid"": ""test""}',
            location_id=location.id,
            floorplan_id=floorplan.id,
        )
        csv = ContentFile(contents)
        response = self.client.post(
            reverse(f"admin:{self.app_label}_device_import"),
            {"format": "0", "import_file": csv, "file_name": "test.csv"},
        )
        self.assertFalse(response.context["result"].has_errors())
        self.assertIn("confirm_form", response.context)
        confirm_form = response.context["confirm_form"]
        data = confirm_form.initial
        response = self.client.post(
            reverse(f"admin:{self.app_label}_device_process_import"), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        device = Device.objects.first()
        self.assertIsNotNone(device)
        # assert geo fields
        self.assertTrue(hasattr(device, "devicelocation"))
        self.assertEqual(device.devicelocation.location, location)
        self.assertEqual(device.devicelocation.floorplan, floorplan)
        self.assertEqual(device.devicelocation.indoor, "-279.21875,442")
        # double check device fields (repetita juvant)
        self.assertEqual(device.name, "test")
        self.assertEqual(device.organization, org)
        self.assertEqual(device.mac_address, "00:11:22:33:44:66")
        self.assertEqual(device.model, "model")
        self.assertEqual(device.os, "os")
        self.assertEqual(device.system, "system")
        self.assertEqual(device.notes, "notes")
        self.assertEqual(device.last_ip, "127.0.0.1")
        self.assertEqual(device.management_ip, "10.0.0.2")
        self.assertTrue(device._has_config())
        self.assertIsNone(device.group)

    def test_device_import_geo_no_floorplan(self):
        org = self._get_org(org_name="default")
        location = self._create_location(
            name="location1org", type="indoor", organization=org
        )
        contents = (
            "name,mac_address,organization,group,model,os,system,notes,venue,address,"
            "coords,is_mobile,venue_type,floor,floor_position,last_ip,management_ip,"
            "config_status,config_backend,config_data,config_context,config_templates,"
            "created,modified,id,key,organization_id,group_id,location_id,floorplan_id\n"  # noqa: E501
            "test,00:11:22:33:44:66,{org_name},,model,os,system,notes,Test,"
            "Via Test 29/c,POINT (-57.63463382632019 -25.28397344703963),False,"
            "indoor,-1,,127.0.0.1,10.0.0.2,applied,netjsonconfig.OpenWrt,"
            '"{config}","{context}",,2022-10-17 15:26:51,2022-10-17 15:26:51,'
            "559871c5-ce3d-4c7e-9176-fb6623d562f3,934d0799b1ce3a454bbb585cda1d7a49,"
            "{org_id},,{location_id},"
        ).strip()
        contents = contents.format(
            org_name=org.name,
            org_id=org.id,
            config='{""general"": {}}',
            context='{""ssid"": ""test""}',
            location_id=location.id,
        )
        csv = ContentFile(contents)
        response = self.client.post(
            reverse(f"admin:{self.app_label}_device_import"),
            {"format": "0", "import_file": csv, "file_name": "test.csv"},
        )
        self.assertFalse(response.context["result"].has_errors())
        self.assertIn("confirm_form", response.context)
        confirm_form = response.context["confirm_form"]
        data = confirm_form.initial
        response = self.client.post(
            reverse(f"admin:{self.app_label}_device_process_import"), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        device = Device.objects.first()
        self.assertIsNotNone(device)
        # assert geo fields
        self.assertTrue(hasattr(device, "devicelocation"))
        self.assertEqual(device.devicelocation.location, location)
        self.assertIsNone(device.devicelocation.floorplan)
        self.assertIsNone(device.devicelocation.indoor)
        # double check device fields (repetita juvant)
        self.assertEqual(device.name, "test")
        self.assertEqual(device.organization, org)
        self.assertEqual(device.mac_address, "00:11:22:33:44:66")
        self.assertEqual(device.model, "model")
        self.assertEqual(device.os, "os")
        self.assertEqual(device.system, "system")
        self.assertEqual(device.notes, "notes")
        self.assertEqual(device.last_ip, "127.0.0.1")
        self.assertEqual(device.management_ip, "10.0.0.2")
        self.assertTrue(device._has_config())
        self.assertIsNone(device.group)
