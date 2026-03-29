from unittest.mock import patch

from django.test import TransactionTestCase

from openwisp_notifications.swapper import load_model, swapper_load_model
from openwisp_notifications.types import NOTIFICATION_TYPES
from openwisp_users.tests.utils import TestOrganizationMixin

NotificationSetting = load_model("NotificationSetting")
OrganizationNotificationSettings = load_model("OrganizationNotificationSettings")
Organization = swapper_load_model("openwisp_users", "Organization")
OrganizationUser = swapper_load_model("openwisp_users", "OrganizationUser")


class TestOrganizationNotificationSettings(TestOrganizationMixin, TransactionTestCase):
    def test_auto_create_delete_notification_setting(self):
        with self.subTest(
            "Creating organization creates OrganizationNotificationSettings"
        ):
            org = self._create_org()
            self.assertEqual(
                OrganizationNotificationSettings.objects.filter(
                    organization=org
                ).count(),
                1,
            )
            org_setting = org.notification_settings
            self.assertEqual(org_setting.web, True)
            self.assertEqual(org_setting.email, True)

        with self.subTest(
            "Deleting organization deletes OrganizationNotificationSettings"
        ):
            org.delete()
            self.assertEqual(
                OrganizationNotificationSettings.objects.filter(
                    organization_id=org.id
                ).count(),
                0,
            )

    def test_changing_web_notification(self):
        org = self._get_org()
        org_setting = org.notification_settings
        org_setting.web = False
        org_setting.full_clean()
        org_setting.save()
        org_setting.refresh_from_db()
        self.assertEqual(org_setting.web, False)
        self.assertEqual(org_setting.email, False)

        with self.subTest("Enabling email notification has no affect"):
            org_setting.email = True
            org_setting.full_clean()
            org_setting.save()
            self.assertEqual(org_setting.email, False)
            self.assertEqual(org_setting.web, False)

    def test_org_setting_changes_user_preferences(self):
        org = self._get_org()
        org_setting = org.notification_settings
        administrator = self._create_administrator(organizations=[org])

        with self.subTest("Disabling web for org disabled all notifications for users"):
            org_setting.web = False
            org_setting.full_clean()
            org_setting.save()
            self.assertEqual(org_setting.email, False)
            self.assertEqual(org_setting.web, False)
            user_settings = NotificationSetting.objects.filter(
                organization=org, user=administrator
            )
            self.assertEqual(user_settings.count(), len(NOTIFICATION_TYPES.keys()))
            for setting in user_settings:
                self.assertEqual(setting.web, False)
                self.assertEqual(setting.email, False)

    def test_new_orguser_uses_org_setting_as_default(self):
        org1 = self._get_org()
        org1_setting = org1.notification_settings
        org1_setting.web = False
        org1_setting.full_clean()
        org1_setting.save()

        org1_user = self._create_org_user(organization=org1, is_admin=True).user
        user_settings = org1_user.notificationsetting_set.filter(
            organization=org1,
        )
        self.assertEqual(user_settings.count(), len(NOTIFICATION_TYPES.keys()))
        for setting in user_settings:
            self.assertEqual(setting.web_notification, False)
            self.assertEqual(setting.email_notification, False)

        org2 = self._create_org(name="Test Org 2")
        org2_setting = org2.notification_settings
        org2_setting.email = False
        org2_setting.full_clean()
        org2_setting.save()

        org2_user = self._create_org_user(organization=org2, is_admin=True).user
        user_settings = org2_user.notificationsetting_set.filter(
            organization=org2,
        )
        self.assertEqual(user_settings.count(), len(NOTIFICATION_TYPES.keys()))

        for setting in user_settings:
            self.assertEqual(setting.web_notification, True)
            self.assertEqual(setting.email_notification, False)

        admin = self._get_admin()
        for setting in admin.notificationsetting_set.filter(organization=org1):
            self.assertEqual(setting.web_notification, False)
            self.assertEqual(setting.email_notification, False)
        for setting in admin.notificationsetting_set.filter(organization=org2):
            self.assertEqual(setting.web_notification, True)
            self.assertEqual(setting.email_notification, False)

    def test_one_setting_object_per_organization(self):
        org = self._get_org()
        org_setting = org.notification_settings
        self.assertEqual(
            OrganizationNotificationSettings.objects.filter(organization=org).count(),
            1,
        )
        # Changing the organization object should not create a new setting
        org.name = "New Org Name"
        org.full_clean()
        org.save()
        org.refresh_from_db()
        self.assertEqual(
            OrganizationNotificationSettings.objects.filter(organization=org).count(),
            1,
        )
        self.assertEqual(
            org.notification_settings.pk,
            org_setting.pk,
        )

    def test_updating_notification_setting_for_deleted_org(self):
        org = self._get_org()
        org_setting = org.notification_settings
        self.assertEqual(org_setting.web, True)
        self.assertEqual(org_setting.email, True)
        org.delete()
        self.assertEqual(
            OrganizationNotificationSettings.objects.filter(
                organization_id=org.pk
            ).count(),
            0,
        )
        with patch.object(NotificationSetting.objects, "update") as mocked_update:
            with self.assertRaises(ValueError):
                org_setting.web = False
                org_setting.save()
        mocked_update.assert_not_called()
