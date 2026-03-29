import csv
from io import StringIO
from ipaddress import ip_address, ip_network

import openpyxl
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from openwisp_users.mixins import ShareableOrgMixin
from openwisp_utils.base import TimeStampedEditableModel
from swapper import get_model_name, load_model

from .fields import NetworkField


class CsvImportException(Exception):
    pass


class AbstractSubnet(ShareableOrgMixin, TimeStampedEditableModel):
    name = models.CharField(max_length=100, db_index=True)
    subnet = NetworkField(
        db_index=True,
        help_text=_(
            'Subnet in CIDR notation, eg: "10.0.0.0/24" '
            'for IPv4 and "fdb6:21b:a477::9f7/64" for IPv6'
        ),
    )
    description = models.CharField(max_length=100, blank=True)
    master_subnet = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="child_subnet_set",
    )

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["subnet"], name="subnet_idx")]
        unique_together = ("subnet", "organization")

    def __str__(self):
        return f"{self.name} {self.subnet}"

    def clean(self):
        if not self.subnet:
            return
        self._validate_multitenant_uniqueness()
        self._validate_multitenant_master_subnet()
        self._validate_multitenant_unique_child_subnet()
        self._validate_overlapping_subnets()
        self._validate_master_subnet_consistency()

    def _validate_multitenant_uniqueness(self):
        qs = self._meta.model.objects.exclude(pk=self.pk).filter(subnet=self.subnet)
        # find out if there's an identical subnet (shared)
        if qs.filter(organization=None).exists():
            raise ValidationError(
                {
                    "subnet": _(
                        "This subnet is already assigned for "
                        "internal usage in the system."
                    )
                }
            )
        # if adding a shared subnet, ensure the subnet
        # is not already taken by another org
        if not self.organization and qs.filter(organization__isnull=False).exists():
            raise ValidationError(
                {
                    "subnet": _(
                        "This subnet is already assigned to another organization."
                    )
                }
            )

    def _validate_multitenant_master_subnet(self):
        if not self.master_subnet:
            return
        if self.master_subnet.organization:
            self._validate_org_relation("master_subnet", field_error="master_subnet")

    def _validate_multitenant_unique_child_subnet(self):
        if self.master_subnet is None or self.master_subnet.organization_id is not None:
            return
        qs = self._meta.model.objects.exclude(id=self.pk).filter(subnet=self.subnet)
        if qs.exists():
            raise ValidationError(
                {
                    "subnet": _(
                        "This subnet is already assigned to another organization."
                    )
                }
            )

    def _validate_overlapping_subnets(self):
        organization_query = Q(organization_id=self.organization_id) | Q(
            organization_id__isnull=True
        )
        error_message = _("Subnet overlaps with {0}.")
        if (
            self.master_subnet and self.master_subnet.organization_id is None
        ) or self.organization is None:
            # The execution of above code implicitly ensures that
            # organization of both master_subnet and current subnet are
            # same. Otherwise, self._validate_multitenant_master_subnet
            # would have raised a validation error
            organization_query = Q()
            error_message = _("Subnet overlaps with a subnet of another organization.")

        qs = self._meta.model.objects.filter(organization_query).only("subnet")
        # exclude parent subnets
        exclude = [self.pk]
        parent_subnet = self.master_subnet
        while parent_subnet:
            exclude.append(parent_subnet.pk)
            parent_subnet = parent_subnet.master_subnet
        # exclude child subnets
        child_subnets = list(self.child_subnet_set.values_list("pk", flat=True))
        while child_subnets:
            exclude += child_subnets
            child_subnets = list(
                self._meta.model.objects.filter(
                    master_subnet__in=child_subnets
                ).values_list("pk", flat=True)
            )
        # exclude also identical subnets (handled by other checks)
        qs = qs.exclude(pk__in=exclude).exclude(subnet=self.subnet)
        for subnet in qs.iterator():
            if ip_network(self.subnet).overlaps(subnet.subnet):
                raise ValidationError({"subnet": error_message.format(subnet.subnet)})

    def _validate_master_subnet_consistency(self):
        if not self.master_subnet:
            return
        subnet_version = ip_network(self.subnet).version
        master_subnet_version = ip_network(self.master_subnet.subnet).version
        if subnet_version != master_subnet_version:
            raise ValidationError(
                {
                    "master_subnet": _(
                        f"IP version mismatch: Subnet {self.subnet} is IPv"
                        f"{subnet_version}, but Master Subnet "
                        f"{self.master_subnet.subnet} is IPv{master_subnet_version}."
                    )
                }
            )
        if not ip_network(self.subnet).subnet_of(ip_network(self.master_subnet.subnet)):
            raise ValidationError({"master_subnet": _("Invalid master subnet.")})

    def get_next_available_ip(self):
        ipaddress_set = [ip.ip_address for ip in self.ipaddress_set.all()]
        subnet_hosts = self.subnet.hosts()
        for host in subnet_hosts:
            if str(host) not in ipaddress_set:
                return str(host)
        return None

    def request_ip(self, options=None):
        if options is None:
            options = {}
        ip = self.get_next_available_ip()
        if not ip:
            return None
        ip_address = load_model("openwisp_ipam", "IpAddress")(
            ip_address=ip, subnet=self, **options
        )
        ip_address.full_clean()
        ip_address.save()
        return ip_address

    def _read_row(self, reader):
        value = next(reader)
        if len(value) > 0:
            return value[0].strip()
        return None

    def _read_subnet_data(self, reader):
        subnet_model = load_model("openwisp_ipam", "Subnet")
        subnet_name = self._read_row(reader)
        subnet_value = self._read_row(reader)
        org_slug = self._read_row(reader)
        subnet_org = self._get_org(org_slug)
        try:
            subnet = subnet_model.objects.get(
                subnet=subnet_value, organization=subnet_org
            )
        except ValidationError as e:
            raise CsvImportException(str(e))
        except subnet_model.DoesNotExist:
            try:
                subnet = subnet_model(
                    name=subnet_name, subnet=subnet_value, organization=subnet_org
                )
                subnet.full_clean()
                subnet.save()
            except ValidationError as e:
                raise CsvImportException(str(e))
        return subnet

    def _read_ipaddress_data(self, reader, subnet):
        ipaddress_model = load_model("openwisp_ipam", "IpAddress")
        ipaddress_list = []
        for row in reader:
            description = str(row[1] or "").strip()
            if not ipaddress_model.objects.filter(
                subnet=subnet,
                ip_address=row[0].strip(),
            ).exists():
                instance = ipaddress_model(
                    subnet=subnet,
                    ip_address=row[0].strip(),
                    description=description,
                )
                try:
                    instance.full_clean()
                except ValueError as e:
                    raise CsvImportException(str(e))
                ipaddress_list.append(instance)
        for ip in ipaddress_list:
            ip.save()

    def _get_csv_reader(self, file):
        if file.name.endswith((".xlsx")):
            book = openpyxl.load_workbook(filename=file)
            sheet = book.worksheets[0]
            reader = sheet.values
        else:
            reader = csv.reader(StringIO(file.read().decode("utf-8")), delimiter=",")
        return reader

    def import_csv(self, file):
        reader = self._get_csv_reader(file)
        subnet = self._read_subnet_data(reader)
        next(reader)
        next(reader)
        self._read_ipaddress_data(reader, subnet)

    def export_csv(self, subnet_id, writer):
        ipaddress_model = load_model("openwisp_ipam", "IpAddress")
        subnet = load_model("openwisp_ipam", "Subnet").objects.get(pk=subnet_id)
        writer.writerow([subnet.name])
        writer.writerow([subnet.subnet])
        writer.writerow([subnet.organization.slug] if subnet.organization else "")
        writer.writerow("")
        fields = [
            ipaddress_model._meta.get_field("ip_address"),
            ipaddress_model._meta.get_field("description"),
        ]
        writer.writerow(field.name for field in fields)
        for obj in subnet.ipaddress_set.all():
            row = []
            for field in fields:
                row.append(str(getattr(obj, field.name)))
            writer.writerow(row)

    def _get_org(self, org_slug):
        Organization = load_model("openwisp_users", "Organization")
        if org_slug in [None, ""]:
            return None
        try:
            validate_slug(org_slug)
            instance = Organization.objects.get(slug=org_slug)
        except ValidationError as e:
            raise CsvImportException(str(e))
        except Organization.DoesNotExist:
            raise CsvImportException(
                "The import operation failed because the data being imported "
                f"belongs to an organization which is not recognized: “{org_slug}”. "
                "Please create this organization or adapt the CSV file being imported "
                "by pointing the data to another organization."
            )
        return instance


class AbstractIpAddress(TimeStampedEditableModel):
    subnet = models.ForeignKey(
        get_model_name("openwisp_ipam", "Subnet"), on_delete=models.CASCADE
    )
    ip_address = models.GenericIPAddressField()
    description = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True
        verbose_name = _("IP address")
        verbose_name_plural = _("IP addresses")

    def __str__(self):
        return self.ip_address

    def clean(self):
        if not self.ip_address or not self.subnet_id:
            return
        if ip_address(self.ip_address) not in self.subnet.subnet:
            raise ValidationError(
                {"ip_address": _("IP address does not belong to the subnet")}
            )
        addresses = (
            load_model("openwisp_ipam", "IpAddress")
            .objects.filter(subnet=self.subnet_id)
            .exclude(pk=self.pk)
            .values()
        )
        for ip in addresses:
            if ip_address(self.ip_address) == ip_address(ip["ip_address"]):
                raise ValidationError({"ip_address": _("IP address already used.")})
