from django.core.management.base import BaseCommand

from openwisp_controller.config.whois.commands import clear_last_ip_command


class Command(BaseCommand):
    help = (
        "Clears the last IP address (if set) for active devices without WHOIS records"
        " across all organizations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do NOT prompt the user for input of any kind.",
        )

    def handle(self, *args, **options):
        clear_last_ip_command(
            stdout=self.stdout,
            stderr=self.stderr,
            interactive=options["interactive"],
        )
