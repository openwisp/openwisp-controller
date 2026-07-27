from datetime import timedelta
from types import SimpleNamespace

import reversion
import swapper
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.template.response import TemplateResponse
from django.urls import path, resolve
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import ReadOnlyAdmin, TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeactivatedDeviceReadOnlyMixin, DeviceAdmin
from .filters import GroupFilter, LocationFilter, TypeFilter
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


class BatchCommandExecutionForm(forms.ModelForm):
    """Form layout for the mass command execution workflow.

    The execution and confirmation behavior is intentionally added separately.
    Keeping the form here lets the custom admin view use the same model fields
    and tenant-scoped choices as the eventual workflow.
    """

    class Meta:
        model = BatchCommand
        fields = [
            "organization",
            "label",
            "notes",
            "type",
            "input",
            "group",
            "location",
            "devices",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "input": forms.Textarea(attrs={"rows": 5}),
            "devices": forms.SelectMultiple(attrs={"size": 8}),
        }

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request is None or request.user.is_superuser:
            return
        organization_ids = request.user.organizations_managed
        for field_name in ("organization", "group", "location", "devices"):
            self.fields[field_name].queryset = self.fields[field_name].queryset.filter(
                organization_id__in=organization_ids
            )


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
    execute_command_template = "admin/connection/batch_command/execute_command.html"
    confirm_command_template = "admin/connection/batch_command/confirm_command.html"
    list_display = [
        "label",
        "organization_display",
        "colored_status",
        "type",
        "affected_devices",
        "created",
    ]
    ordering = ("-created",)
    list_filter = [
        MultitenantOrgFilter,
        "status",
        TypeFilter,
        GroupFilter,
        LocationFilter,
    ]
    list_select_related = ("organization",)
    search_fields = [
        "label",
        "notes",
        "organization__name",
        "devices__name",
        "location__name",
        "group__name",
    ]
    change_form_template = (
        "admin/connection/batch_command/batch_command_change_form.html"
    )
    device_commands_per_page = 20
    exclude = ("devices",)
    fields = [
        "organization_display",
        "label",
        "notes",
        "colored_status",
        "type",
        "formatted_input",
        "affected_devices",
        "group",
        "location",
        "display_skipped_devices",
        "created",
        "modified",
    ]
    readonly_fields = [
        "organization_display",
        "colored_status",
        "type",
        "formatted_input",
        "affected_devices",
        "display_skipped_devices",
        "group",
        "location",
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

    def get_urls(self):
        options = self.model._meta
        return [
            path(
                "execute/",
                self.admin_site.admin_view(self.execute_command_view),
                name=f"{options.app_label}_{options.model_name}_execute",
            ),
            path(
                "confirm/",
                self.admin_site.admin_view(self.confirm_command_view),
                name=f"{options.app_label}_{options.model_name}_confirm",
            ),
        ] + super().get_urls()

    def execute_command_view(self, request):
        """Render the first step of the mass command workflow.

        This page only collects command details for now. The preview and
        confirmation POST flow will be added in a later change.
        """
        permission = f"{self.opts.app_label}.add_{self.opts.model_name}"
        if not request.user.has_perm(permission):
            raise PermissionDenied
        form = BatchCommandExecutionForm(request=request)
        context = {
            **self.admin_site.each_context(request),
            "title": _("Execute mass command"),
            "opts": self.model._meta,
            "form": form,
            "media": self.media + form.media,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(request, self.execute_command_template, context)

    def confirm_command_view(self, request):
        """Render the second step of the mass command workflow.

        Displays a summary of the command to be executed and provides
        an Execute button to create the BatchCommand.
        """
        permission = f"{self.opts.app_label}.add_{self.opts.model_name}"
        if not request.user.has_perm(permission):
            raise PermissionDenied
        command_type = request.GET.get("type", "")
        label = request.GET.get("label", "")
        notes = request.GET.get("notes", "")
        organization_id = request.GET.get("organization", "")
        group_id = request.GET.get("group", "")
        location_id = request.GET.get("location", "")
        device_ids = request.GET.getlist("devices")

        command_type_display = command_type
        command_description = ""
        for choice_value, choice_label in BatchCommand._meta.get_field("type").choices:
            if choice_value == command_type:
                command_type_display = choice_label
                break

        targets_parts = []
        if organization_id:
            Organization = swapper.load_model("openwisp_users", "Organization")
            try:
                org = Organization.objects.get(pk=organization_id)
                targets_parts.append(str(org))
            except Organization.DoesNotExist:
                pass
        if group_id:
            DeviceGroup = swapper.load_model("config", "DeviceGroup")
            try:
                group = DeviceGroup.objects.get(pk=group_id)
                targets_parts.append(str(group))
            except DeviceGroup.DoesNotExist:
                pass
        if location_id:
            Location = swapper.load_model("geo", "Location")
            try:
                location = Location.objects.get(pk=location_id)
                targets_parts.append(str(location))
            except Location.DoesNotExist:
                pass
        targets_display = (
            ", ".join(targets_parts) if targets_parts else _("All devices")
        )

        device_count = len(device_ids) if device_ids else 0
        skipped_devices_count = 0

        context = {
            **self.admin_site.each_context(request),
            "title": _("Review mass command"),
            "opts": self.model._meta,
            "command_type_display": command_type_display,
            "command_description": command_description,
            "targets_display": targets_display,
            "device_count": device_count,
            "skipped_devices_count": skipped_devices_count,
            "media": self.media,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(request, self.confirm_command_template, context)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return fields + list(self.__class__.readonly_fields)

    def _get_commands(self, request, obj):
        qs = Command.objects.filter(batch_command=obj).select_related("device")
        if not request.user.is_superuser:
            qs = qs.filter(
                device__organization_id__in=request.user.organizations_managed
            )
        return qs

    def organization_display(self, obj):
        if obj.organization:
            return obj.organization.name
        # Will return Shared systemwide (no organization) after
        # https://github.com/openwisp/openwisp-users/issues/238
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
        pks = list(obj.skipped_devices.keys())
        devices = {str(d.pk): d for d in Device.objects.filter(pk__in=pks)}
        count = len(pks)
        lines = [str(count)]
        for pk_str, errors in obj.skipped_devices.items():
            device = devices.get(pk_str)
            name = device.name if device else _("Deleted ({})").format(pk_str)
            lines.append(format_html("{}: {}", name, ", ".join(errors)))
        return format_html(
            '<div class="skipped-devices-list">{}</div>',
            format_html_join(mark_safe("<br>"), "{}", ((line,) for line in lines)),
        )

    display_skipped_devices.short_description = _("skipped devices")

    def _build_filter_specs(
        self,
        request,
        obj,
        current_status,
        current_location=None,
        current_group=None,
        current_org=None,
    ):
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
            (("", _("All")),) + Command.STATUS_CHOICES + (("skipped", _("skipped")),)
        ):
            status_choices.append(
                _make_choice(current_status, display_name, "status", status_value)
            )

        class StatusFilter:
            title = _("status")
            choices = status_choices

        filter_specs.append(StatusFilter())

        Device = swapper.load_model("config", "Device")

        # Location filter
        location_spec = self._build_related_filter(
            _("location"),
            "location_id",
            current_location or "",
            Device.objects.filter(command__batch_command=obj)
            .exclude(devicelocation__location__isnull=True)
            .values_list(
                "devicelocation__location__id",
                "devicelocation__location__name",
            )
            .distinct(),
            _make_choice,
        )
        if location_spec:
            filter_specs.append(location_spec)

        # Group filter
        group_spec = self._build_related_filter(
            _("device group"),
            "group_id",
            current_group or "",
            Device.objects.filter(
                command__batch_command=obj,
                group__isnull=False,
            )
            .values_list("group__id", "group__name")
            .distinct(),
            _make_choice,
        )
        if group_spec:
            filter_specs.append(group_spec)

        # Organization filter (superusers only)
        if request.user.is_superuser:
            org_spec = self._build_related_filter(
                _("organization"),
                "organization_id",
                current_org or "",
                Device.objects.filter(command__batch_command=obj)
                .values_list("organization__id", "organization__name")
                .distinct(),
                _make_choice,
            )
            if org_spec:
                filter_specs.append(org_spec)

        return filter_specs

    def _build_related_filter(self, title, param_name, current_value, qs, make_choice):
        choices = [make_choice(current_value, _("All"), param_name, "")]
        for obj_id, obj_name in qs:
            if obj_id:
                choices.append(
                    make_choice(current_value, obj_name, param_name, str(obj_id))
                )
        if len(choices) <= 1:
            return None
        return SimpleNamespace(title=title, choices=choices)

    def _paginate_commands(self, items, page_param, per_page=None):
        per_page = per_page or self.device_commands_per_page
        paginator = Paginator(list(items), per_page)
        page_number = page_param or 1
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        return page_obj, paginator, page_obj.object_list

    def _get_active_filters(self, request):
        return {
            "q": request.GET.get("q", ""),
            "status": request.GET.get("status", ""),
            "location_id": request.GET.get("location_id", ""),
            "group_id": request.GET.get("group_id", ""),
            "organization_id": request.GET.get("organization_id", ""),
        }

    def _apply_command_filters(self, qs, filters):
        if filters["q"]:
            qs = qs.filter(device__name__icontains=filters["q"])
        status = filters["status"]
        if status and status != "skipped":
            qs = qs.filter(status=status)
        if filters["location_id"]:
            qs = qs.filter(device__devicelocation__location_id=filters["location_id"])
        if filters["group_id"]:
            qs = qs.filter(device__group_id=filters["group_id"])
        if filters["organization_id"]:
            qs = qs.filter(device__organization_id=filters["organization_id"])
        return qs

    def _get_matching_skipped_devices(self, obj, filters):
        Device = swapper.load_model("config", "Device")
        pks = list(obj.skipped_devices.keys())
        device_qs = Device.objects.filter(pk__in=pks)
        location_id = filters["location_id"]
        if location_id:
            DeviceLocation = swapper.load_model("geo", "DeviceLocation")
            device_locations = set(
                DeviceLocation.objects.filter(
                    device_id__in=pks,
                    location_id=location_id,
                ).values_list("device_id", flat=True)
            )
        else:
            device_locations = None
        devices = {str(d.pk): d for d in device_qs}
        rows = []
        for pk_str, errors in obj.skipped_devices.items():
            device = devices.get(pk_str)
            if not device:
                continue
            if (
                filters["organization_id"]
                and str(device.organization_id) != filters["organization_id"]
            ):
                continue
            if filters["group_id"] and str(device.group_id) != filters["group_id"]:
                continue
            if device_locations is not None and pk_str not in device_locations:
                continue
            if filters["q"] and filters["q"].lower() not in device.name.lower():
                continue
            rows.append(
                {
                    "device_name": device.name,
                    "device_pk": pk_str,
                    "status": "skipped",
                    "status_display": _("skipped"),
                    "output": ", ".join(errors),
                    "created": None,
                    "is_skipped": True,
                }
            )
        return rows

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            commands_qs = self._get_commands(request, obj)
            filters = self._get_active_filters(request)
            commands_qs = self._apply_command_filters(commands_qs, filters)
            rows = [
                {
                    "device_name": cmd.device.name,
                    "device_pk": cmd.device.pk,
                    "status": cmd.status,
                    "status_display": cmd.get_status_display(),
                    "output": (cmd.output or "").lstrip(),
                    "created": cmd.created,
                    "is_skipped": False,
                }
                for cmd in commands_qs
            ]
            if obj.skipped_devices and filters["status"] in ("", "skipped"):
                rows.extend(self._get_matching_skipped_devices(obj, filters))
            # Sort by status priority: success(0) > failed(1) > skipped(2), then alphabetically
            rows.sort(
                key=lambda r: (
                    {"success": 0, "failed": 1, "skipped": 2}.get(r["status"], 99),
                    r["device_name"].lower(),
                )
            )
            filter_specs = self._build_filter_specs(
                request,
                obj,
                filters["status"],
                current_location=filters["location_id"],
                current_group=filters["group_id"],
                current_org=filters["organization_id"],
            )
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
