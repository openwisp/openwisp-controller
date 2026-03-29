import csv
from ipaddress import ip_network

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext_lazy as _

from openwisp_ipam.base.models import CsvImportException


class BaseImportSubnetCommand(BaseCommand):
    help = _("Import an entire Subnet data from a csv/xls/xlsx file")

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, help="File path to import csv data.")

    def handle(self, *args, **options):
        file = options["file"]
        try:
            if not file.endswith((".csv", ".xls", ".xlsx")):
                raise CommandError(_("File type not supported"))
            with open(file, "rb+") as csvfile:
                try:
                    self.subnet_model().import_csv(csvfile)
                except CsvImportException as e:
                    raise CommandError(str(e))
            csvfile.close()
        except FileNotFoundError:
            raise CommandError(_('File "%s" not found.' % file))
        self.stdout.write(self.style.SUCCESS(_('Successfully imported "%s"' % file)))


class BaseExportSubnetCommand(BaseCommand):
    help = _("Export an entire Subnet data as a csv file")

    def add_arguments(self, parser):
        parser.add_argument("subnet", type=str, help=_("Subnet to export."))

    def handle(self, *args, **options):
        subnet = options["subnet"]
        try:
            instance = self.subnet_model.objects.get(subnet=ip_network(subnet))
        except self.subnet_model.DoesNotExist:
            raise CommandError(_('Subnet "%s" does not exist' % subnet))
        except ValueError:
            raise CommandError(
                _("'%s' does not appear to be an IPv4 or IPv6 network" % subnet)
            )
        with open("data_{0}.csv".format(instance.id), "w+") as csvfile:
            writer = csv.writer(csvfile, delimiter=",")
            instance.export_csv(instance.id, writer)
            csvfile.close()
        self.stdout.write(self.style.SUCCESS(_("Successfully exported %s" % subnet)))
