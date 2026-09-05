import hashlib
import logging
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import reversion
import swapper
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.http import (
    HttpResponseForbidden,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, resolve
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from openwisp_users.multitenancy import MultitenantOrgFilter
from openwisp_utils.admin import ReadOnlyAdmin, TimeReadonlyAdminMixin

from ..admin import MultitenantAdminMixin
from ..config.admin import DeactivatedDeviceReadOnlyMixin, DeviceAdmin
from .commands import ORGANIZATION_COMMAND_SCHEMA
from .filters import GroupFilter, LocationFilter, TypeFilter
from .schema import schema
from .widgets import (
    BatchCommandSchemaWidget,
    CommandSchemaWidget,
    CredentialsSchemaWidget,
    OrganizationScopedSelect,
)

logger = logging.getLogger(__name__)

Credentials = swapper.load_model("connection", "Credentials")
DeviceConnection = swapper.load_model("connection", "DeviceConnection")
Command = swapper.load_model("connection", "Command")
BatchCommand = swapper.load_model("connection", "BatchCommand")
Device = swapper.load_model("config", "Device")
DeviceGroup = swapper.load_model("config", "DeviceGroup")
Location = swapper.load_model("geo", "Location")
Organization = swapper.load_model("openwisp_users", "Organization")


class CredentialsForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {"params": CredentialsSchemaWidget}


class CommandForm(forms.ModelForm):
    class Meta:
        exclude = []
        widgets = {"input": CommandSchemaWidget}


class BatchCommandExecutionForm(forms.ModelForm):
    required_css_class = "required"
    devices = forms.CharField(widget=forms.HiddenInput, required=False)

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
        ]
        widgets = {
            "label": forms.TextInput(attrs={"class": "vTextField ow-text-field"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "input": BatchCommandSchemaWidget,
            "group": OrganizationScopedSelect,
            "location": OrganizationScopedSelect,
        }

    class Media:
        js = [
            "admin/js/vendor/jquery/jquery.min.js",
            "admin/js/vendor/select2/select2.full.min.js",
            "admin/js/jquery.init.js",
            "connection/js/execute-command.js",
        ]
        css = {
            "screen": [
                "admin/css/vendor/select2/select2.min.css",
                "admin/css/autocomplete.css",
            ]
        }

    def __init__(self, *args, request=None, device_ids=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.device_ids = self._scope_devices(device_ids)
        if self.device_ids:
            self.fields["devices"].initial = ",".join(self.device_ids)
            for field_name in ("organization", "group", "location"):
                self.fields[field_name].disabled = True
            self.fields["organization"].initial = self._selected_organization_id()
        if request is None or request.user.is_superuser:
            return
        organization_ids = request.user.organizations_managed
        self.fields["organization"].queryset = self.fields[
            "organization"
        ].queryset.filter(id__in=organization_ids)
        for field_name in ("group", "location"):
            self.fields[field_name].queryset = self.fields[field_name].queryset.filter(
                organization_id__in=organization_ids
            )
        allowed_commands = {}
        for organization_id in organization_ids:
            allowed_commands.update(
                dict(Command.get_org_allowed_commands(organization_id=organization_id))
            )
        empty_choices = [
            choice for choice in self.fields["type"].choices if not choice[0]
        ]
        self.fields["type"].choices = empty_choices + list(allowed_commands.items())

    def _scope_devices(self, device_ids):
        self._organization_ids = set()
        self._dropped_devices = False
        if not device_ids:
            return []
        devices = Device.objects.filter(pk__in=device_ids)
        if self.request is not None and not self.request.user.is_superuser:
            devices = devices.filter(
                organization_id__in=self.request.user.organizations_managed
            )
        rows = list(devices.values_list("pk", "organization_id"))
        self._organization_ids = {row[1] for row in rows}
        self._dropped_devices = len(rows) != len(set(device_ids))
        return [str(row[0]) for row in rows]

    def _selected_organization_id(self):
        if len(self._organization_ids) != 1:
            return None
        return str(next(iter(self._organization_ids)))

    def clean(self):
        cleaned_data = super().clean()
        if self._dropped_devices:
            raise ValidationError(
                _("Some of the selected devices are no longer available.")
            )
        if len(self._organization_ids) > 1:
            raise ValidationError(
                _("All devices must belong to the same organization.")
            )
        if self.request is None or self.request.user.is_superuser:
            return cleaned_data
        organization = cleaned_data.get("organization")
        group = cleaned_data.get("group")
        location = cleaned_data.get("location")
        # a batch without any target would run on every device of the
        # deployment, which only superusers are allowed to do
        if not self.device_ids and not any([organization, group, location]):
            raise ValidationError(
                _(
                    "Please select at least one of: organization, device group,"
                    " or location."
                )
            )
        # "organizations_managed" is a list of organization UUIDs as strings
        organization_ids = self.request.user.organizations_managed
        related_organizations = (
            ("organization", organization.pk if organization else None),
            ("group", group.organization_id if group else None),
            ("location", location.organization_id if location else None),
        )
        for field_name, organization_id in related_organizations:
            if organization_id is None:
                continue
            if str(organization_id) not in organization_ids:
                self.add_error(field_name, _("Select a valid choice."))
        return cleaned_data

    def to_session(self):
        """Returns the cleaned values as JSON serializable primitives.

        The session uses the JSON serializer, so model instances and UUIDs
        cannot be stored as they are.
        """

        def _pk(value):
            return str(value.pk) if value else None

        return {
            # Namespaces the device selection the confirm page keeps in
            # sessionStorage, which lives as long as the browser tab: without
            # it a wizard would inherit the devices unselected by a previous
            # one. It has to be issued here rather than by the browser,
            # because the session is shared between tabs and sessionStorage
            # is not. It is also submitted back on execution, which runs
            # only the wizard the confirm page was rendered with.
            "token": uuid4().hex,
            "type": self.cleaned_data["type"],
            "label": self.cleaned_data["label"],
            "notes": self.cleaned_data.get("notes") or "",
            "input": self.cleaned_data.get("input"),
            "organization_id": _pk(self.cleaned_data.get("organization")),
            "group_id": _pk(self.cleaned_data.get("group")),
            "location_id": _pk(self.cleaned_data.get("location")),
            "device_ids": self.device_ids,
        }


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


class BatchCommandDeviceAdminMixin:
    """Applied on top of the ModelAdmin registered for Device, for
    openwisp-monitoring which replaces that registration and
    its extra columns must appear.

    Filters and search are emptied because the devices are already chosen on
    the execute page, this table only excludes some of them.
    """

    list_display_links = ["name"]
    list_filter = []
    search_fields = []
    actions = None
    list_per_page = 20
    ordering = ["name"]
    change_list_template = "admin/connection/batch_command/confirm_command.html"
    import_export_change_list_template = None

    def __init__(self, model, admin_site, devices=None):
        super().__init__(model, admin_site)
        self.devices = devices

    def get_list_display(self, request):
        return ["select_device"] + list(super().get_list_display(request))

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk__in=self.devices)

    @admin.display(description="")
    def select_device(self, obj):
        return format_html(
            '<input type="checkbox" class="device-checkbox" value="{}"'
            ' aria-label="{}" checked>',
            obj.pk,
            _("Include {}").format(obj.name),
        )


class BatchCommandAdmin(MultitenantAdminMixin, ReadOnlyAdmin):
    execute_command_template = "admin/connection/batch_command/execute_command.html"
    confirm_command_template = "admin/connection/batch_command/confirm_command.html"
    session_key = "batch_command_wizard"
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
        "display_skipped_devices",
        "group",
        "location",
        "created",
        "modified",
    ]
    readonly_fields = [
        "organization_display",
        "colored_status",
        "formatted_input",
        "affected_devices",
        "display_skipped_devices",
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
            path(
                "ui/schema.json",
                self.admin_site.admin_view(self.schema_view),
                name=f"{options.app_label}_{options.model_name}_schema",
            ),
        ] + super().get_urls()

    def _check_add_permission(self, request):
        permission = f"{self.opts.app_label}.add_{self.opts.model_name}"
        if not request.user.has_perm(permission):
            raise PermissionDenied

    def schema_view(self, request):
        """Returns the schemas of the command types the wizard offers.

        The type choices are the union over the organizations the user
        manages, so the schemas are too: the editor fetches them once on
        page load, before an organization has been picked.
        """
        self._check_add_permission(request)
        schemas = {}
        if request.user.is_superuser:
            for organization_schemas in ORGANIZATION_COMMAND_SCHEMA.values():
                schemas.update(organization_schemas)
        else:
            for organization_id in request.user.organizations_managed:
                schemas.update(
                    Command.get_org_schema(organization_id=organization_id) or {}
                )
        return JsonResponse(schemas)

    @staticmethod
    def _wizard_initial(wizard):
        return {
            "type": wizard.get("type"),
            "input": wizard.get("input"),
            "label": wizard.get("label"),
            "notes": wizard.get("notes"),
            "organization": wizard.get("organization_id"),
            "group": wizard.get("group_id"),
            "location": wizard.get("location_id"),
        }

    def execute_command_view(self, request):
        """First step of the mass command workflow: collect the details.
        A valid submission goes to the session and redirects to the confirm
        page, so that its device table can be paginated with plain GETs.
        """
        if request.method not in ("GET", "POST"):
            return HttpResponseNotAllowed(["GET", "POST"])
        self._check_add_permission(request)
        if request.method == "POST":
            form = BatchCommandExecutionForm(
                request.POST,
                request=request,
                device_ids=self._get_pk_list(request.POST, "devices"),
            )
            if form.is_valid():
                request.session[self.session_key] = form.to_session()
                return redirect(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_confirm"
                )
        else:
            wizard = request.session.get(self.session_key)
            if request.GET.get("back") and wizard:
                form = BatchCommandExecutionForm(
                    initial=self._wizard_initial(wizard), request=request
                )
            else:
                request.session.pop(self.session_key, None)
                form = BatchCommandExecutionForm(request=request)
        return self._render_execute_page(request, form)

    def _render_execute_page(self, request, form, system_wide=False):
        device_count = len(form.device_ids)
        if device_count:
            messages.warning(
                request,
                ngettext(
                    "The command will run on the device you selected.",
                    "The command will run on the %(count)d devices you selected.",
                    device_count,
                )
                % {"count": device_count},
            )
        elif system_wide:
            messages.warning(request, _("The command will run on all devices."))
        context = {
            **self.admin_site.each_context(request),
            "title": _("Execute mass command"),
            "opts": self.opts,
            "form": form,
            "media": form.media,
            "has_view_permission": self.has_view_permission(request),
            "device_count": device_count,
            "system_wide": system_wide,
        }
        return TemplateResponse(request, self.execute_command_template, context)

    def confirm_command_view(self, request):
        """Second step: review the targeted devices and dispatch the command.
        Dispatching is decided by the HTTP method alone.
        """
        if request.method not in ("GET", "POST"):
            return HttpResponseNotAllowed(["GET", "POST"])
        self._check_add_permission(request)
        if request.method == "POST":
            return self._execute_batch_command(request)
        wizard = request.session.get(self.session_key)
        if not wizard:
            return self._restart(request)
        devices = self._resolve_target_queryset(request, wizard)
        digest = self._devices_digest(devices.values_list("pk", flat=True))
        if wizard.get("devices_digest") not in (None, digest):
            wizard["token"] = uuid4().hex
        wizard["devices_digest"] = digest
        request.session[self.session_key] = wizard
        device_admin = self.get_device_admin(devices)
        # changelist_view() assembles the whole changelist context (cl,
        # media, pagination) and renders the change_list_template of the
        # mixin, which is the confirm page extending the stock changelist
        # template
        return device_admin.changelist_view(
            request, extra_context=self._confirm_context(request, wizard, devices)
        )

    def get_device_admin(self, devices):
        """Builds the ModelAdmin rendering the device table of the confirm page.
        Composed with whichever ModelAdmin is registered for Device, so the
        table shows the columns of the device changelist as it actually is:
        openwisp-monitoring replaces that registration to add its own.
        Resolved per request, when the registration is final.
        """
        registered = self.admin_site.get_model_admin(Device).__class__
        # the mixin comes first so that its attributes win over the
        # registered admin's
        device_admin_class = type(
            "BatchCommandDeviceAdmin",
            (BatchCommandDeviceAdminMixin, registered),
            {"readonly_fields": list(registered.readonly_fields)},
        )
        return device_admin_class(Device, self.admin_site, devices=devices)

    def get_device_changelist_template(self):
        """The template the registered Device admin renders its changelist with.
        The confirm page extends it rather than the stock one, because that
        is where other modules load the assets their columns need. Read from
        the class: django-import-export rewrites it on the instance.
        """
        registered = self.admin_site.get_model_admin(Device).__class__
        return getattr(registered, "change_list_template", None) or (
            "admin/change_list.html"
        )

    def _restart(self, request):
        """Sends the user back to step one when there is no wizard to show."""
        self.message_user(
            request,
            _("Please fill in the mass command details to continue."),
            messages.WARNING,
        )
        return redirect(f"admin:{self.opts.app_label}_{self.opts.model_name}_execute")

    def _resolve_target_queryset(self, request, wizard):
        """Devices picked one by one, or matched by the organization, group
        and location chosen. The targeting rule lives on the model so this
        page and the execution cannot drift apart; the multitenancy scope and
        the ordering the pagination needs are admin concerns, applied on top.
        """
        device_ids = wizard.get("device_ids")
        if device_ids:
            devices = Device.objects.filter(pk__in=device_ids)
        else:
            try:
                devices = BatchCommand.dry_run(
                    organization_id=wizard.get("organization_id"),
                    group_id=wizard.get("group_id"),
                    location_id=wizard.get("location_id"),
                )["devices"]
            except (ObjectDoesNotExist, ValidationError) as error:
                logger.warning(
                    "Failed to resolve devices for mass command wizard"
                    " (organization_id=%s, group_id=%s, location_id=%s): %s",
                    wizard.get("organization_id"),
                    wizard.get("group_id"),
                    wizard.get("location_id"),
                    error,
                )
                return Device.objects.none()
        if not request.user.is_superuser:
            devices = devices.filter(
                organization_id__in=request.user.organizations_managed
            )
        return devices.distinct().order_by("name")

    def _devices_digest(self, device_ids):
        """Identifies the set of devices a confirm page was rendered with,
        so that only the reviewed set is executed.
        """
        pks = sorted(str(pk) for pk in device_ids)
        return hashlib.sha256(",".join(pks).encode()).hexdigest()

    def _confirm_context(self, request, wizard, devices):
        device_count = devices.count()
        targets = []
        for model, key in (
            (Organization, "organization_id"),
            (DeviceGroup, "group_id"),
            (Location, "location_id"),
        ):
            if not wizard.get(key):
                continue
            target = model.objects.filter(pk=wizard[key]).first()
            if target:
                targets.append(str(target))
        command_types = dict(BatchCommand._meta.get_field("type").choices)
        return {
            "title": _("Review mass command"),
            "batch_opts": self.opts,
            # the template this page extends, see get_device_changelist_template()
            "device_changelist_template": self.get_device_changelist_template(),
            "wizard": wizard,
            "command_type_display": command_types.get(wizard["type"], wizard["type"]),
            "command_description": self._describe_input(wizard.get("input")),
            "targets_display": self._targets_display(wizard, targets, device_count),
            "device_count": device_count,
            "has_view_permission": self.has_view_permission(request),
        }

    def _targets_display(self, wizard, targets, device_count):
        if wizard.get("device_ids"):
            return ngettext(
                "%(count)d selected device", "%(count)d selected devices", device_count
            ) % {"count": device_count}
        return ", ".join(targets) if targets else _("All devices")

    def _describe_input(self, command_input):
        """Renders the submitted input for the review step, so that every
        registered command type is shown and not only custom ones.
        """
        if not isinstance(command_input, dict):
            return ""
        if "command" in command_input:
            return command_input["command"]
        return ", ".join(
            f"{key}: {value}"
            for key, value in command_input.items()
            if "password" not in key.lower()
        )

    def _execute_batch_command(self, request):
        """Applies the device selection and dispatches the mass command.
        Only the wizard the confirm page was rendered with is executed, and
        it is removed before the batch is created, so a double submit finds
        nothing and restarts.
        """
        wizard = request.session.get(self.session_key)
        if not wizard or request.POST.get("token") != wizard.get("token"):
            return self._restart(request)
        del request.session[self.session_key]
        devices = self._resolve_target_queryset(request, wizard)
        device_ids = list(devices.values_list("pk", flat=True))
        if self._devices_digest(device_ids) != wizard.get("devices_digest"):
            request.session[self.session_key] = wizard
            self.message_user(
                request,
                _("The targeted devices changed, please review them again."),
                messages.WARNING,
            )
            return redirect(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_confirm"
            )
        # The confirm page only lists the devices matched on the execute
        # page, so the selection can only ever remove from that set: the
        # browser never supplies a device to add.
        excluded = self._get_pk_list(request.POST, "excluded")
        selection = Device.objects.filter(pk__in=device_ids).exclude(pk__in=excluded)
        kwargs = {
            "type": wizard["type"],
            "label": wizard["label"],
            "input": wizard.get("input"),
            "notes": wizard.get("notes") or "",
            "organization_id": wizard.get("organization_id"),
            "group_id": wizard.get("group_id"),
            "location_id": wizard.get("location_id"),
            "devices": list(selection),
            "system_wide": request.user.is_superuser
            and not any(
                (
                    wizard.get("organization_id"),
                    wizard.get("group_id"),
                    wizard.get("location_id"),
                )
            ),
        }
        try:
            batch = BatchCommand.execute(**kwargs)
        except ObjectDoesNotExist as error:
            logger.warning(
                "Failed to execute mass command wizard"
                " (organization_id=%s, group_id=%s, location_id=%s): %s",
                wizard.get("organization_id"),
                wizard.get("group_id"),
                wizard.get("location_id"),
                error,
            )
            return self._restart(request)
        except ValidationError as error:
            # put the wizard back so the user can correct the selection
            request.session[self.session_key] = wizard
            self.message_user(request, error.messages[0], messages.ERROR)
            return redirect(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_confirm"
            )
        self.message_user(
            request, _("Mass command executed successfully."), messages.SUCCESS
        )
        return redirect(
            f"admin:{self.opts.app_label}_{self.opts.model_name}_change", batch.pk
        )

    @staticmethod
    def _get_uuid(value):
        try:
            return str(UUID(str(value)))
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _get_pk_list(source, name):
        pks = (
            BatchCommandAdmin._get_uuid(pk) for pk in source.get(name, "").split(",")
        )
        return [pk for pk in pks if pk]

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return fields + list(self.__class__.readonly_fields)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_affected_devices=Count("batch_commands", distinct=True))
        )

    def get_object(self, request, object_id, from_field=None):
        """Avoids duplicating queries in change_view custom logic"""
        cache_attr = f"_cached_object_{object_id}_{from_field}"
        if not hasattr(request, cache_attr):
            setattr(
                request, cache_attr, super().get_object(request, object_id, from_field)
            )
        return getattr(request, cache_attr)

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
        if obj.type == "change_password":
            return "********"
        return self._describe_input(obj.input) or "-"

    formatted_input.short_description = _("input")

    def affected_devices(self, obj):
        count = getattr(obj, "_affected_devices", None)
        if count is None:
            count = obj.affected_devices
        return count

    affected_devices.short_description = _("affected devices")
    affected_devices.admin_order_field = "_affected_devices"

    def display_skipped_devices(self, obj):
        if not obj.skipped_count:
            return "-"
        rows = obj.get_skipped_preview()
        lines = [str(obj.skipped_count)]
        lines += [
            format_html("{}: {}", row["device_name"], row["output"]) for row in rows
        ]
        if len(rows) < obj.skipped_count:
            lines.insert(-1, "\u2026")
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
        params.pop("page", None)

        def _make_choice(current_value, display, param_name, value):
            q = params.copy()
            q.pop(param_name, None)
            if value:
                q[param_name] = value
            qs = q.urlencode()
            query_string = f"?{qs}"
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

        filter_specs.append(SimpleNamespace(title=_("status"), choices=status_choices))

        batch_devices = Device.objects.filter(
            Q(command__batch_command=obj) | Q(pk__in=obj.skipped_device_ids)
        )
        if not request.user.is_superuser:
            batch_devices = batch_devices.filter(
                organization_id__in=request.user.organizations_managed
            )

        # Location filter
        location_spec = self._build_related_filter(
            _("location"),
            "location_id",
            current_location or "",
            batch_devices.exclude(devicelocation__location__isnull=True)
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
            batch_devices.filter(group__isnull=False)
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
                batch_devices.values_list(
                    "organization__id", "organization__name"
                ).distinct(),
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

    @staticmethod
    def _command_row(command):
        return {
            "device_name": command.device.name,
            "device": command.device.pk,
            "status": command.status,
            "status_display": command.get_status_display(),
            "output": command.output_preview,
            "modified": command.modified,
            "is_skipped": False,
        }

    def _paginate_commands(
        self, batch, commands_qs, skipped_items, page_param, per_page=None
    ):
        """Returns one page of rows without loading the whole batch in memory.
        Commands keep the ordering of ``AbstractCommand.Meta`` ("created"),
        so the newest is always last and the change page can append results
        live. Skipped devices are not Command rows, they come as a list and
        follow the commands.
        """
        per_page = per_page or self.device_commands_per_page
        commands_count = commands_qs.count()
        total = commands_count + len(skipped_items)
        paginator = Paginator(range(total), per_page)
        try:
            page_obj = paginator.page(page_param or 1)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)
        start = (page_obj.number - 1) * per_page
        end = start + per_page
        commands_end = min(end, commands_count)
        rows = [
            self._command_row(command) for command in commands_qs[start:commands_end]
        ]
        skipped_start = max(0, start - commands_count)
        skipped_end = max(0, end - commands_count)
        rows += batch.get_skipped_rows(skipped_start, skipped_end, items=skipped_items)
        return page_obj, paginator, rows

    def _get_active_filters(self, request):
        return {
            "q": request.GET.get("q", ""),
            "status": request.GET.get("status", ""),
            "location_id": self._get_uuid(request.GET.get("location_id", "")),
            "group_id": self._get_uuid(request.GET.get("group_id", "")),
            "organization_id": self._get_uuid(request.GET.get("organization_id", "")),
        }

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        if obj:
            commands_qs = self._get_commands(request, obj)
            filters = self._get_active_filters(request)
            commands_qs = obj.filter_commands(commands_qs, filters)
            skipped_items = []
            if obj.skipped_count and filters["status"] in ("", "skipped"):
                skipped_items = obj.filter_skipped_items(filters)
            page_obj, paginator, commands = self._paginate_commands(
                obj, commands_qs, skipped_items, request.GET.get("page", 1)
            )
            filter_specs = self._build_filter_specs(
                request,
                obj,
                filters["status"],
                current_location=filters["location_id"],
                current_group=filters["group_id"],
                current_org=filters["organization_id"],
            )
            extra_context.update(
                {
                    "commands": commands,
                    "page_obj": page_obj,
                    "paginator": paginator,
                    "filter_specs": filter_specs,
                    "has_active_filters": any(
                        value for key, value in filters.items() if key != "q"
                    ),
                    "device_opts": Device._meta,
                    "status_labels": {
                        status: str(label)
                        for status, label in (
                            *BatchCommand.STATUS_CHOICES,
                            *Command.STATUS_CHOICES,
                            ("skipped", _("skipped")),
                        )
                    },
                }
            )
        return super().change_view(request, object_id, extra_context=extra_context)

    @staticmethod
    @admin.action(description=_("Execute mass command"), permissions=["change"])
    def execute_mass_command_admin_action(modeladmin, request, queryset):
        """Second entry point of the mass command workflow: the devices are
        picked one by one instead of being matched by organization, group or
        location. The selection travels in the form rather than in the session,
        so it cannot outlive the wizard it belongs to.
        """
        batch_admin = modeladmin.admin_site.get_model_admin(BatchCommand)
        batch_admin._check_add_permission(request)
        organization_ids = set(queryset.values_list("organization_id", flat=True))
        if len(organization_ids) > 1:
            if request.user.is_superuser and queryset.count() == Device.objects.count():
                return batch_admin._render_execute_page(
                    request,
                    BatchCommandExecutionForm(request=request),
                    system_wide=True,
                )
            modeladmin.message_user(
                request,
                _("All devices must belong to the same organization."),
                messages.ERROR,
            )
            return HttpResponseRedirect(request.get_full_path())
        form = BatchCommandExecutionForm(
            request=request,
            device_ids=[str(pk) for pk in queryset.values_list("pk", flat=True)],
        )
        return batch_admin._render_execute_page(request, form)


admin.site.register(BatchCommand, BatchCommandAdmin)
DeviceAdmin.actions += [BatchCommandAdmin.execute_mass_command_admin_action]
