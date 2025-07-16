from unittest import mock

from django.urls import reverse
from django.utils.translation import gettext as _
from openwisp_notifications.signals import notify
from swapper import load_model

from ..tests.utils import CreateConfigMixin

Device = load_model("config", "Device")
WHOISInfo = load_model("config", "WHOISInfo")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")

MESSAGE_MAP = {
    "device_error": {
        "message": _(
            "Failed to fetch WHOIS details for device"
            " [{notification.target}]({notification.target_link})"
        ),
        "description": _("WHOIS details could not be fetched for ip: {ip_address}."),
        "level": "error",
    },
    "location_error": {
        "message": _(
            "Unable to create approximate location for device "
            "[{notification.target}]({notification.target_link}). "
            "Please assign/create a location manually."
        ),
        "description": _("Multiple devices found for IP: {ip_address}"),
        "level": "error",
    },
    "location_created": {
        "message": _(
            "Approximate location [{notification.actor}]({notification.actor_link})"
            " for device"
            " [{notification.target}]({notification.target_link}#devicelocation-group)"
            " created successfully."
        ),
        "description": _("Location created for IP: {ip_address}"),
        "level": "info",
    },
    "location_updated": {
        "message": _(
            "Approximate location [{notification.actor}]({notification.actor_link})"
            " for device"
            " [{notification.target}]({notification.target_link}#devicelocation-group)"
            " updated successfully."
        ),
        "description": _("Location updated for IP: {ip_address}"),
        "level": "info",
    },
}


def send_whois_task_notification(device_pk, notify_type, actor=None):
    device = Device.objects.get(pk=device_pk)
    notify_details = MESSAGE_MAP[notify_type]
    notify.send(
        sender=actor or device,
        type="generic_message",
        target=device,
        action_object=device,
        level=notify_details["level"],
        message=notify_details["message"],
        description=notify_details["description"].format(ip_address=device.last_ip),
    )


class CreateWHOISMixin(CreateConfigMixin):
    def _create_whois_info(self, **kwargs):
        options = dict(
            ip_address="172.217.22.14",
            address={
                "city": "Mountain View",
                "country": "United States",
                "continent": "North America",
                "postal": "94043",
            },
            asn="15169",
            isp="Google LLC",
            timezone="America/Los_Angeles",
            cidr="172.217.22.0/24",
            longitude=150.0,
            latitude=50.0,
        )

        options.update(kwargs)
        w = WHOISInfo(**options)
        w.full_clean()
        w.save()
        return w

    def setUp(self):
        super().setUp()
        OrganizationConfigSettings.objects.create(
            organization=self._get_org(), whois_enabled=True
        )


class WHOISTransactionMixin:
    @staticmethod
    def _mocked_client_response():
        mock_response = mock.MagicMock()
        mock_response.city.name = "Mountain View"
        mock_response.country.name = "United States"
        mock_response.continent.name = "North America"
        mock_response.postal.code = "94043"
        mock_response.traits.autonomous_system_organization = "Google LLC"
        mock_response.traits.autonomous_system_number = 15169
        mock_response.traits.network = "172.217.22.0/24"
        mock_response.location.time_zone = "America/Los_Angeles"
        mock_response.location.latitude = 50
        mock_response.location.longitude = 150
        return mock_response

    def _task_called(self, mocked_task, task_name="WHOIS lookup"):
        org = self._get_org()

        with self.subTest(f"{task_name} task called when last_ip is public"):
            with mock.patch("django.core.cache.cache.set") as mocked_set:
                device = self._create_device(last_ip="172.217.22.14")
                mocked_task.assert_called()
                mocked_set.assert_called_once()
        mocked_task.reset_mock()

        with self.subTest(
            f"{task_name} task called when last_ip is changed and is public"
        ):
            with mock.patch("django.core.cache.cache.get") as mocked_get:
                device.last_ip = "172.217.22.10"
                device.save()
                mocked_task.assert_called()
                # The cache `get` is called twice, once for `whois_enabled` and
                # once for `approximate_location_enabled`
                mocked_get.assert_called()
        mocked_task.reset_mock()

        with self.subTest(f"{task_name} task not called when last_ip is private"):
            device.last_ip = "10.0.0.1"
            device.save()
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest(f"{task_name} task not called when WHOIS is disabled"):
            Device.objects.all().delete()
            org.config_settings.whois_enabled = False
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["whois_enabled"])
            device = self._create_device(last_ip="172.217.22.14")
            mocked_task.assert_not_called()
        mocked_task.reset_mock()

        with self.subTest(
            f"{task_name} task called via DeviceChecksumView when WHOIS is enabled"
        ):
            org.config_settings.whois_enabled = True
            # Invalidates old org config settings cache
            org.config_settings.save(update_fields=["whois_enabled"])
            # config is required for checksum view to work
            self._create_config(device=device)
            # setting remote address field to a public IP to trigger WHOIS task
            # since the view uses this header for tracking the device's IP
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR="172.217.22.10",
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
        mocked_task.reset_mock()

        with self.subTest(
            f"{task_name} task called via DeviceChecksumView for no WHOIS record"
        ):
            WHOISInfo.objects.all().delete()
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_called()
        mocked_task.reset_mock()

        with self.subTest(
            f"{task_name} task not called via DeviceChecksumView when WHOIS is disabled"
        ):
            WHOISInfo.objects.all().delete()
            org.config_settings.whois_enabled = False
            org.config_settings.save(update_fields=["whois_enabled"])
            response = self.client.get(
                reverse("controller:device_checksum", args=[device.pk]),
                {"key": device.key},
                REMOTE_ADDR=device.last_ip,
            )
            self.assertEqual(response.status_code, 200)
            mocked_task.assert_not_called()
        mocked_task.reset_mock()
