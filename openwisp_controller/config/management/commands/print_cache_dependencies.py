from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _

from openwisp_controller.config.base.cache import CacheDependency


class Command(BaseCommand):
    help = _(
        "Prints every cache dependency wired in the project, so the whole"
        " cache invalidation graph can be inspected at a glance."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help=_("Output format (default: text)."),
        )

    def handle(self, *args, **options):
        self.stdout.write(CacheDependency.render_registered(fmt=options["format"]))
