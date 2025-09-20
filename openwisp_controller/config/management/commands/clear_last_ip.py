from django.core.management.base import BaseCommand, CommandError
from django.db.models import OuterRef, Subquery
from swapper import load_model


class Command(BaseCommand):
    help = "Clear the last IP address, if set, of active devices of all organizations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do NOT prompt the user for input of any kind.",
        )
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        Device = load_model("config", "Device")
        WHOISInfo = load_model("config", "WHOISInfo")

        if options["interactive"]:
            message = ["\n"]
            message.append(
                "This will clear last IP of all active devices across organizations!\n"
            )
            message.append(
                "Are you sure you want to do this?\n\n"
                "Type 'yes' to continue, or 'no' to cancel: "
            )
            if input("".join(message)) != "yes":
                raise CommandError("Operation cancelled by user.")

        devices = Device.objects.filter(_is_deactivated=False).only("last_ip")
        # Filter devices that have no WHOIS information for their last IP
        devices = devices.exclude(last_ip=None).exclude(
            last_ip__in=Subquery(
                WHOISInfo.objects.filter(ip_address=OuterRef("last_ip")).values(
                    "ip_address"
                )
            ),
        )

        updated_devices = devices.update(last_ip=None)
        if updated_devices:
            self.stdout.write(
                f"Cleared last IP addresses for {updated_devices} active device(s)."
            )
        else:
            self.stdout.write("No active devices with last IP to clear.")
