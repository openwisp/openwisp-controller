from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_loci.tests.base.test_admin import BaseTestAdmin
from swapper import load_model

from ...tests.utils import TestAdminMixin
from .utils import TestGeoMixin

Device = load_model('config', 'Device')
Location = load_model('geo', 'Location')
FloorPlan = load_model('geo', 'FloorPlan')
DeviceLocation = load_model('geo', 'DeviceLocation')


class TestAdmin(TestAdminMixin, TestGeoMixin, BaseTestAdmin, TestCase):
    app_label = 'geo'
    object_model = Device
    location_model = Location
    floorplan_model = FloorPlan
    object_location_model = DeviceLocation
    user_model = get_user_model()

    def setUp(self):
        """override TestAdminMixin.setUp"""
        pass

    def _create_multitenancy_test_env(self, vpn=False):
        org1 = self._create_organization(name='test1org')
        org2 = self._create_organization(name='test2org')
        inactive = self._create_organization(name='inactive-org', is_active=False)
        operator = self._create_operator(organizations=[org1, inactive])
        l1 = self._create_location(
            name='location1org', type='indoor', organization=org1
        )
        l2 = self._create_location(
            name='location2org', type='indoor', organization=org2
        )
        l3 = self._create_location(
            name='location-inactive', type='indoor', organization=inactive
        )
        fl1 = self._create_floorplan(location=l1, organization=org1)
        fl2 = self._create_floorplan(location=l2, organization=org2)
        fl3 = self._create_floorplan(location=l3, organization=inactive)
        d1 = self._create_object(
            name='org1-dev',
            organization=org1,
            key='key1',
            mac_address='00:11:22:33:44:56',
        )
        d2 = self._create_object(
            name='org2-dev',
            organization=org2,
            key='key2',
            mac_address='00:12:22:33:44:56',
        )
        d3 = self._create_object(
            name='org3-dev',
            organization=inactive,
            key='key3',
            mac_address='00:13:22:33:44:56',
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
            url=reverse(f'admin:{self.app_label}_location_changelist'),
            visible=[data['l1'].name, data['org1'].name],
            hidden=[
                data['l2'].name,
                data['org2'].name,
                data['inactive'].name,
                data['l3_inactive'].name,
            ],
        )

    def test_location_organization_fk_queryset(self):
        self._create_admin()
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_location_add'),
            visible=[data['org1'].name],
            hidden=[data['org2'].name, data['inactive']],
            select_widget=True,
        )

    def test_floorplan_queryset(self):
        self._create_admin()
        data = self._create_multitenancy_test_env()
        self._test_multitenant_admin(
            url=reverse(f'admin:{self.app_label}_floorplan_changelist'),
            visible=[data['fl1'], data['org1'].name],
            hidden=[
                data['fl2'],
                data['org2'].name,
                data['inactive'].name,
                data['fl3_inactive'],
            ],
        )

    def test_admin_menu_groups(self):
        # Test menu group (openwisp-utils menu group) for Location , FloorPlan

        self.client.force_login(self._create_admin())
        models = ['location', 'floorplan']
        response = self.client.get(reverse('admin:index'))
        for model in models:
            with self.subTest(f'test menu group link for {model} model'):
                url = reverse(f'admin:{self.app_label}_{model}_changelist')
                self.assertContains(response, f' class="mg-link" href="{url}"')
        with self.subTest('test "Geographic Info" group is registered'):
            self.assertContains(
                response,
                '<div class="mg-dropdown-label">Geographic Info </div>',
                html=True,
            )
