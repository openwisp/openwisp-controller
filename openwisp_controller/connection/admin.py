import json
from datetime import timedelta

import reversion
import swapper
from django import forms
from django.contrib import admin
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.urls import path, resolve
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import ReadOnlyAdmin, TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeactivatedDeviceReadOnlyMixin, DeviceAdmin
from .schema import schema
from .widgets import CommandSchemaWidget, CredentialsSchemaWidget

Credentials = swapper.load_model("connection", "Credentials")
DeviceConnection = swapper.load_model("connection", "DeviceConnection")
Command = swapper.load_model("connection", "Command")
BatchCommand = swapper.load_model("connection", "BatchCommand")


class CredentialsForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {"params": CredentialsSchemaWidget}


class CommandForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {"input": CommandSchemaWidget}


@admin.register(Credentials)
class CredentialsAdmin(MultitenantAdminMixin, TimeReadonlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "connector",
        "auto_add",
        "created",
        "modified",
    )
    list_filter = [MultitenantOrgFilter, "connector"]
    list_select_related = ("organization",)
    form = CredentialsForm
    fields = [
        "connector",
        "name",
        "organization",
        "auto_add",
        "params",
        "created",
        "modified",
    ]

    def get_urls(self):
        options = getattr(self.model, "_meta")
        url_prefix = f"{options.app_label}_{options.model_name}"
        return [
            path(
                "ui/schema.json",
                self.admin_site.admin_view(self.schema_view),
                name=f"{url_prefix}_schema",
            )
        ] + super().get_urls()

    def schema_view(self, request):
        return JsonResponse(schema)


class DeviceConnectionInline(
    MultitenantAdminMixin, DeactivatedDeviceReadOnlyMixin, admin.StackedInline
):
    model = DeviceConnection
    verbose_name = _("Credentials")
    verbose_name_plural = verbose_name
    exclude = ["params", "created", "modified"]
    readonly_fields = ["is_working", "failure_reason", "last_attempt"]
    extra = 0

    multitenant_shared_relations = ("credentials",)

    def get_queryset(self, request):
        """
        Override MultitenantAdminMixin.get_queryset() because it breaks
        """
        return super(admin.StackedInline, self).get_queryset(request)


class LimitedCommandResults(forms.models.BaseInlineFormSet):
    """Limits results to 30"""

    def get_queryset(self):
        return super().get_queryset()[0:30]


class CommandInline(admin.StackedInline):
    model = Command
    verbose_name = _("Recent Commands")
    verbose_name_plural = verbose_name
    fields = [
        "status_display",
        "type",
        "input_data",
        "output_data",
        "created",
        "modified",
    ]
    readonly_fields = [
        "status_display",
        "type",
        "input_data",
        "output_data",
        "created",
        "modified",
    ]
    formset = LimitedCommandResults

    def get_queryset(self, request, select_related=True):
        """
        Return the most recent commands for this device
        (created within the last 7 days)
        """
        qs = super().get_queryset(request)
        resolved = resolve(request.path_info)
        if "object_id" in resolved.kwargs:
            seven_days = localtime() - timedelta(days=7)
            qs = qs.filter(
                device_id=resolved.kwargs["object_id"], created__gte=seven_days
            ).order_by("-created")
        if select_related:
            qs = qs.select_related()
        return qs

    def input_data(self, obj):
        return obj.input_data

    def output_data(self, obj):
        if obj.status == "in-progress":
            return format_html(
                '<div class="loader recent-commands-loader"></div>',
            )
        return obj.output

    def status_display(self, obj):
        status_value = obj.status
        css_class = f"command-status {status_value}"
        return format_html(
            '<span class="{0}">{1}</span>',
            css_class,
            obj.get_status_display(),
        )

    input_data.short_description = _("input")
    output_data.short_description = _("output")
    status_display.short_description = _("status")

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return self.get_queryset(request, select_related=select_related).exists()

    def has_delete_permission(self, request, obj):
        return False

    def has_add_permission(self, request, obj):
        return False

    def has_change_permission(self, request, obj):
        return False


class CommandWritableInline(DeactivatedDeviceReadOnlyMixin, admin.StackedInline):
    model = Command
    extra = 1
    form = CommandForm
    fields = ["type", "input"]

    def get_queryset(self, request, select_related=True):
        return self.model.objects.none()

    def _get_conditional_queryset(self, request, obj, select_related=False):
        return bool(obj) and self.has_change_permission(request, obj)

    def get_urls(self):
        options = self.model._meta
        url_prefix = f"{options.app_label}_{options.model_name}"
        return [
            path(
                f"{options.app_label}/{options.model_name}/ui/schema.json",
                self.admin_site.admin_view(self.schema_view),
                name=f"{url_prefix}_schema",
            ),
        ]

    def schema_view(self, request):
        organization_id = request.GET.get("organization_id")
        if not request.user.is_superuser and (
            not organization_id or not request.user.is_manager(organization_id)
        ):
            return HttpResponseForbidden()
        result = self.model.get_org_schema(organization_id=organization_id)
        return JsonResponse(result)


DeviceAdmin.inlines += [DeviceConnectionInline]
reversion.register(model=DeviceConnection, follow=["device"])
DeviceAdmin.conditional_inlines += [
    CommandWritableInline,
    # this inline must come after CommandWritableInline
    # or the JS logic will not work
    CommandInline,
]
DeviceAdmin.add_reversion_following(follow=["deviceconnection_set"])


class BatchCommandAdmin(MultitenantAdminMixin, ReadOnlyAdmin):
    ordering = ("-created",)
    list_display = [
        "label",
        "organization_display",
        "colored_status",
        "type",
        "affected_devices",
        "created",
    ]
    list_display_links = ["label"]
    list_filter = [MultitenantOrgFilter, "status", "type"]
    list_select_related = ("organization",)
    search_fields = ["label"]
    change_form_template = (
        "admin/connection/batch_command/batch_command_change_form.html"
    )
    device_commands_per_page = 20
    exclude = ("devices",)
    fields = [
        "organization_display",
        "label",
        "notes",
        "affected_devices",
        "colored_status",
        "type",
        "formatted_input",
        "group",
        "location",
        "display_skipped_devices",
        "created",
        "modified",
    ]

    class Media:
        css = {
            "all": [
                "admin/css/changelists.css",
                "admin/css/ow-filters.css",
                "connection/css/batch-command.css",
            ]
        }
        js = [
            "admin/js/ow-filter.js",
            "connection/js/batch-command.js",
        ]

    def get_readonly_fields(self, request, obj=None):
        return self.fields or []

    def organization_display(self, obj):
        if obj.organization:
            return obj.organization.name
        return _("All")

    organization_display.short_description = _("organization")
    organization_display.admin_order_field = "organization"

    def colored_status(self, obj):
        css_class = f"command-status {obj.status}"
        return format_html(
            '<span class="{0}">{1}</span>',
            css_class,
            obj.get_status_display(),
        )

    colored_status.short_description = _("status")

    def formatted_input(self, obj):
        if not obj.input:
            return "-"
        return obj.input.get("command", obj.input)

    formatted_input.short_description = _("input")

    def affected_devices(self, obj):
        return obj.affected_devices

    affected_devices.short_description = _("affected devices")

    def display_skipped_devices(self, obj):
        if not obj.skipped_devices:
            return "-"
        Device = swapper.load_model("config", "Device")
        count = len(obj.skipped_devices)
        lines = [str(count)]
        for pk_str, errors in obj.skipped_devices.items():
            device = Device.objects.filter(pk=pk_str).first()
            name = device.name if device else _("Deleted ({})").format(pk_str)
            lines.append(format_html("{}: {}", name, ", ".join(errors)))
        return format_html(
            '<div class="skipped-devices-list">{}</div>',
            format_html_join(mark_safe("<br>"), "{}", ((line,) for line in lines)),
        )

    display_skipped_devices.short_description = _("Skipped devices")

    def _build_filter_specs(self, request, current_status):
        filter_specs = []
        params = request.GET.copy()

        def _make_choice(current_value, display, param_name, value):
            q = params.copy()
            q.pop(param_name, None)
            if value:
                q[param_name] = value
            qs = q.urlencode()
            query_string = f"?{qs}" if qs else ""
            return {
                "display": display,
                "selected": current_value == value,
                "query_string": query_string,
            }

        status_choices = []
        for status_value, display_name in (
            (("", _("All")),) + Command.STATUS_CHOICES + (("skipped", _("Skipped")),)
        ):
            status_choices.append(
                _make_choice(current_status, display_name, "status", status_value)
            )

        class StatusFilter:
            title = _("status")
            choices = status_choices

        filter_specs.append(StatusFilter())
        return filter_specs

    def _paginate_commands(self, items, page_param, per_page=None):
        per_page = per_page or self.device_commands_per_page
        paginator = Paginator(list(items), per_page)
        page_number = page_param or 1
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        return page_obj, paginator, page_obj.object_list

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            Device = swapper.load_model("config", "Device")
            commands_qs = Command.objects.filter(batch_command=obj).select_related(
                "device"
            )
            search_query = request.GET.get("q", "")
            if search_query:
                commands_qs = commands_qs.filter(device__name__icontains=search_query)
            current_status = request.GET.get("status", "")
            if current_status and current_status != "skipped":
                commands_qs = commands_qs.filter(status=current_status)
            rows = []
            for cmd in commands_qs:
                rows.append(
                    {
                        "device_name": cmd.device.name,
                        "device_pk": cmd.device.pk,
                        "status": cmd.status,
                        "status_display": cmd.get_status_display(),
                        "output": (cmd.output or "").lstrip(),
                        "created": cmd.created,
                        "is_skipped": False,
                    }
                )
            if obj.skipped_devices and current_status in ("", "skipped"):
                for pk_str, errors in obj.skipped_devices.items():
                    device = Device.objects.filter(pk=pk_str).first()
                    name = device.name if device else _("Deleted ({})").format(pk_str)
                    if search_query and search_query.lower() not in name.lower():
                        continue
                    rows.append(
                        {
                            "device_name": name,
                            "device_pk": pk_str,
                            "status": "skipped",
                            "status_display": _("Skipped"),
                            "output": ", ".join(errors),
                            "created": None,
                            "is_skipped": True,
                        }
                    )

            def _sort_key(row):
                priority = {"success": 0, "failed": 1, "skipped": 2}
                return (priority.get(row["status"], 99), row["device_name"].lower())

            rows.sort(key=_sort_key)
            filter_specs = self._build_filter_specs(request, current_status)
            page_obj, paginator, commands = self._paginate_commands(
                rows, request.GET.get("page", 1)
            )
            extra_context.update(
                {
                    "commands": commands,
                    "page_obj": page_obj,
                    "paginator": paginator,
                    "filter_specs": filter_specs,
                    "has_active_filters": any(
                        request.GET.get(param) for param in ["status"]
                    ),
                }
            )
        return super().change_view(request, object_id, extra_context=extra_context)


admin.site.register(BatchCommand, BatchCommandAdmin)
