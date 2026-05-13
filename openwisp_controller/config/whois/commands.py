from django.core.management.base import CommandError
from django.db.models import OuterRef, Subquery
from swapper import load_model

from openwisp_controller.config import settings as app_settings


def clear_last_ip_command(stdout, stderr, interactive=True):
    """
    Clears the last IP address (if set) for active devices without WHOIS records
    across all organizations.
    """
    if not app_settings.WHOIS_CONFIGURED:
        raise CommandError(
            "WHOIS lookup is not configured. Set "
            "OPENWISP_CONTROLLER_WHOIS_GEOIP_ACCOUNT "
            "and OPENWISP_CONTROLLER_WHOIS_GEOIP_KEY to enable this command."
        )

    Device = load_model("config", "Device")
    WHOISInfo = load_model("config", "WHOISInfo")

    if interactive:  # pragma: no cover
        message = ["\n"]
        message.append(
            "This will clear the last IP of any active device which doesn't "
            "have WHOIS info yet!\n"
        )
        message.append(
            "Are you sure you want to do this?\n\n"
            "Type 'yes' to continue, or 'no' to cancel: "
        )
        if input("".join(message)).lower() != "yes":
            raise CommandError("Operation cancelled by user.")

    devices = (
        Device.objects.filter(_is_deactivated=False).select_related(
            "organization__config_settings"
        )
        # include the FK field 'organization' in .only() so the related
        # `organization__config_settings` traversal is not deferred
        .only("last_ip", "organization", "key")
    )
    # Filter out devices that have WHOIS information for their last IP
    devices = devices.exclude(last_ip=None).exclude(
        last_ip__in=Subquery(
            WHOISInfo.objects.filter(ip_address=OuterRef("last_ip")).values(
                "ip_address"
            )
        ),
    )
    # We cannot use a queryset-level update here because it bypasses model save()
    # and signals, which are required to properly invalidate related caches
    # (e.g. DeviceChecksumView.get_device). To ensure correct behavior and
    # future compatibility, each device is saved individually.
    updated_devices = 0
    for device in devices.iterator():
        device.last_ip = None
        device.save(update_fields=["last_ip"])
        updated_devices += 1
    if updated_devices:
        stdout.write(
            f"Cleared the last IP addresses for {updated_devices} active device(s)."
        )
    else:
        stdout.write("No active devices with last IP to clear.")
