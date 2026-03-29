import csv
from collections import OrderedDict
from copy import deepcopy
from functools import update_wrapper

import swapper
from django import forms
from django.contrib import admin, messages
from django.contrib.admin import ModelAdmin
from django.db.models import TextField
from django.db.models.functions import Cast
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, re_path, reverse
from django.utils.translation import gettext_lazy as _
from openwisp_users.multitenancy import MultitenantAdminMixin, MultitenantOrgFilter
from openwisp_utils.admin import TimeReadonlyAdminMixin
from rest_framework.exceptions import PermissionDenied
from reversion.admin import VersionAdmin

from .api.utils import AuthorizeCSVOrgManaged, CsvImportAPIException
from .api.views import HostsSet
from .base.forms import IpAddressImportForm
from .base.models import CsvImportException
from .filters import SubnetFilter, SubnetOrganizationFilter

Subnet = swapper.load_model("openwisp_ipam", "Subnet")
IpAddress = swapper.load_model("openwisp_ipam", "IpAddress")


@admin.register(Subnet)
class SubnetAdmin(
    VersionAdmin,
    MultitenantAdminMixin,
    TimeReadonlyAdminMixin,
    ModelAdmin,
    AuthorizeCSVOrgManaged,
):
    app_label = "openwisp_ipam"
    change_form_template = "admin/openwisp-ipam/subnet/change_form.html"
    change_list_template = "admin/openwisp-ipam/subnet/change_list.html"
    list_display = [
        "name",
        "organization",
        "subnet",
        "master_subnet",
        "created",
        "modified",
    ]
    list_filter = [MultitenantOrgFilter]
    autocomplete_fields = ["master_subnet"]
    search_fields = ["subnet", "name"]
    list_select_related = ["organization", "master_subnet"]
    save_on_top = True

    def change_view(self, request, object_id, form_url="", extra_context=None):
        instance = self.get_object(request, object_id)
        if instance is None:
            # This is an internal Django method that redirects the
            # user to the admin index page with a message that points
            # out that the requested object does not exist.
            return self._get_obj_does_not_exist_redirect(
                request, self.model._meta, object_id
            )
        ipaddress_add_url = "admin:{0}_ipaddress_add".format(self.app_label)
        ipaddress_change_url = "admin:{0}_ipaddress_change".format(self.app_label)
        subnet_change_url = "admin:{0}_subnet_change".format(self.app_label)
        if request.GET.get("_popup"):
            return super().change_view(request, object_id, form_url, extra_context)
        # Find root master_subnet for subnet tree
        instance_root = instance
        while instance_root.master_subnet:
            instance_root = instance_root.master_subnet
        # Get instances for all subnets for root master_subnet
        instance_subnets = Subnet.objects.filter(
            subnet=instance_root.subnet, organization=instance_root.organization
        ).values("master_subnet", "pk", "name", "subnet")
        # Make subnet tree
        collection_depth = 0
        subnet_tree = [instance_subnets]
        while instance_subnets:
            instance_subnets = Subnet.objects.none()
            for slave_subnet in subnet_tree[collection_depth]:
                instance_subnets = instance_subnets | Subnet.objects.filter(
                    master_subnet=slave_subnet["pk"]
                ).values("master_subnet", "pk", "name", "subnet")
            subnet_tree.append(instance_subnets)
            collection_depth += 1

        used = instance.ipaddress_set.count()

        # Storing UUID corresponding to respective IP address in a dictionary
        ip_id_list = (
            IpAddress.objects.filter(subnet=instance)
            .annotate(str_id=Cast("id", output_field=TextField()))
            .values_list("ip_address", "str_id")
        )

        # Converting UUIdField to String and then modifying to convert back to uuid form
        ip_id_list = OrderedDict(ip_id_list)
        ip_uuid = {}
        for ip_addr, Ip in ip_id_list.items():
            ip_uuid[ip_addr] = f"{Ip[0:8]}-{Ip[8:12]}-{Ip[12:16]}-{Ip[16:20]}-{Ip[20:]}"
        available = HostsSet(instance).count() - used
        labels = ["Used", "Available"]
        values = [used, available]
        extra_context = {
            "labels": labels,
            "values": values,
            "original": instance,
            "ip_uuid": ip_uuid,
            "ipaddress_add_url": ipaddress_add_url,
            "ipaddress_change_url": ipaddress_change_url,
            "subnet_change_url": subnet_change_url,
            "subnet_tree": subnet_tree,
        }
        return super().change_view(request, object_id, form_url, extra_context)

    def _check_perm(self, view, perm):
        admin_site = self.admin_site

        def inner(request, *args, **kwargs):
            if not request.user.has_perm(f"{self.app_label}.{perm}"):
                return redirect(
                    reverse("admin:index", current_app=admin_site.name),
                )
            return view(request, *args, **kwargs)

        return update_wrapper(inner, view)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path(
                r"^(?P<subnet_id>[^/]+)/export-subnet/",
                self._check_perm(self.export_view, "change_subnet"),
                name="ipam_export_subnet",
            ),
            path(
                "import-subnet/",
                self._check_perm(self.import_view, "add_subnet"),
                name="ipam_import_subnet",
            ),
        ]
        return custom_urls + urls

    def export_view(self, request, subnet_id):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="ip_address.csv"'
        writer = csv.writer(response)
        Subnet().export_csv(subnet_id, writer)
        return response

    def import_view(self, request):
        form = IpAddressImportForm()
        form_template = "admin/openwisp-ipam/subnet/import.html"
        subnet_list_url = f"admin:{self.app_label}_{Subnet._meta.model_name}_changelist"
        context = {
            "form": form,
            "subnet_list_url": subnet_list_url,
            "has_permission": True,
        }
        if request.method == "POST":
            form = IpAddressImportForm(request.POST, request.FILES)
            context["form"] = form
            if form.is_valid():
                file = request.FILES["csvfile"]
                try:
                    self.assert_organization_permissions(request)
                except (PermissionDenied, CsvImportAPIException) as e:
                    messages.error(request, str(e))
                    return redirect(reverse(context["subnet_list_url"]))
                if not file.name.endswith((".csv", ".xls", ".xlsx")):
                    messages.error(request, _("File type not supported."))
                    return render(request, form_template, context)
                try:
                    Subnet().import_csv(file)
                except CsvImportException as e:
                    messages.error(request, str(e))
                    return render(request, form_template, context)
                messages.success(request, _("Successfully imported data."))
                return redirect(reverse(context["subnet_list_url"]))
        return render(request, form_template, context)

    def get_csv_organization(self, request):
        data = Subnet._get_csv_reader(self, deepcopy(request.FILES["csvfile"]))
        return Subnet._get_org(self, org_slug=list(data)[2][0].strip())

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "admin/js/SelectBox.js",
            "openwisp-ipam/js/subnet.js",
            "openwisp-ipam/js/minified/jstree.min.js",
            "openwisp-ipam/js/minified/plotly.min.js",
        )
        css = {
            "all": (
                "openwisp-ipam/css/admin.css",
                "openwisp-ipam/css/minified/jstree.min.css",
            )
        }


class IpAddressAdminForm(forms.ModelForm):
    class Meta:
        help_texts = {
            "subnet": _(
                "Select a subnet and the first available IP address "
                "will be automatically suggested in the ip address field"
            )
        }


@admin.register(IpAddress)
class IpAddressAdmin(
    VersionAdmin, MultitenantAdminMixin, TimeReadonlyAdminMixin, ModelAdmin
):
    form = IpAddressAdminForm
    change_form_template = "admin/openwisp-ipam/ip_address/change_form.html"
    list_display = ["ip_address", "subnet", "organization", "created", "modified"]
    list_filter = [SubnetOrganizationFilter, SubnetFilter]
    search_fields = ["ip_address"]
    autocomplete_fields = ["subnet"]
    multitenant_parent = "subnet"
    list_select_related = ["subnet", "subnet__organization"]
    save_on_top = True

    class Media:
        js = (
            "admin/js/jquery.init.js",
            "openwisp-ipam/js/ip-request.js",
        )

    def organization(self, obj):
        return obj.subnet.organization

    organization.short_description = _("organization")

    def get_extra_context(self):
        url = reverse("ipam:get_next_available_ip", args=["0000"])
        return {"get_next_available_ip_url": url}

    def add_view(self, request, form_url="", extra_context=None):
        return super().add_view(request, form_url, self.get_extra_context())

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return super().change_view(
            request, object_id, form_url, self.get_extra_context()
        )

    def response_add(self, request, *args, **kwargs):
        """
        Custom reponse to dismiss an add form popup for IP address.
        """
        response = super().response_add(request, *args, **kwargs)
        if request.POST.get("_popup"):
            return HttpResponse(
                f"""
<script type='text/javascript'>
    opener.dismissAddAnotherPopup(window, '{request.POST.get('ip_address')}');
</script>
                """
            )
        return response

    def response_change(self, request, *args, **kwargs):
        """
        Custom reponse to dismiss a change form popup for IP address.
        """
        response = super().response_change(request, *args, **kwargs)
        if request.POST.get("_popup"):
            return HttpResponse(
                """
<script type='text/javascript'>
    opener.dismissAddAnotherPopup(window);
</script>
             """
            )
        return response
