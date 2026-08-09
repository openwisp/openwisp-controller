from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import reversion
import swapper
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
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
from . import settings as app_settings
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
    """Collects the mass command details on the first step of the workflow.

    This form is the only place where the submitted values are validated.
    Narrowing the querysets in ``__init__`` controls what the widgets offer,
    it does not control what is accepted, so ``clean()`` re-checks the
    submitted values against the organizations the user actually manages.
    """

    required_css_class = "required"

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
            "notes": forms.Textarea(attrs={"rows": 3}),
            # filled in by execute-command.js, which renders the fields
            # relevant to the selected command type
            "input": forms.HiddenInput(),
        }

    class Media:
        # select2 must be loaded before jquery.init.js, which calls
        # jQuery.noConflict(): same ordering as admin.widgets.AutocompleteMixin
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

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
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

    def clean(self):
        cleaned_data = super().clean()
        if self.request is None or self.request.user.is_superuser:
            return cleaned_data
        organization = cleaned_data.get("organization")
        group = cleaned_data.get("group")
        location = cleaned_data.get("location")
        # a batch without any target would run on every device of the
        # deployment, which only superusers are allowed to do
        if not any([organization, group, location]):
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
            # is not. Not a security token: it only scopes a storage key.
            "token": uuid4().hex,
            "type": self.cleaned_data["type"],
            "label": self.cleaned_data["label"],
            "notes": self.cleaned_data.get("notes") or "",
            "input": self.cleaned_data.get("input"),
            "organization_id": _pk(self.cleaned_data.get("organization")),
            "group_id": _pk(self.cleaned_data.get("group")),
            "location_id": _pk(self.cleaned_data.get("location")),
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
    """Turns the device changelist into the selection table of the confirm page.

    Applied on top of whichever ModelAdmin is registered for Device rather
    than on top of this module's DeviceAdmin, because other modules replace
    that registration: openwisp-monitoring unregisters Device and registers
    its own subclass, which adds the health status column. Building on the
    registered class means those columns appear here too, along with the
    select_related and the media they need, without this module knowing
    which ones exist. See BatchCommandAdmin.get_device_admin().

    Filters and search are removed on purpose: the devices are already
    determined by the targets chosen on the execute page, this table only
    allows excluding individual devices from that set. Emptying
    ``list_filter`` and ``search_fields`` is enough for the stock changelist
    template to render neither, so it can be reused as it is.
    """

    # DeviceAdmin leaves this as an empty tuple, which ModelAdmin reads as
    # "link the first column": that would wrap the checkbox in an <a> and
    # navigate to the device instead of ticking it. Name is the column the
    # device changelist links anyway.
    list_display_links = ["name"]
    list_filter = []
    search_fields = []
    actions = None
    list_per_page = 20
    ordering = ["name"]
    change_list_template = "admin/connection/batch_command/confirm_command.html"
    # django-import-export replaces change_list_template on the instance with
    # a template of its own, which redefines the object-tools block and so
    # brings back the "Import", "Export" and "Add device" buttons this page
    # suppresses. Setting this to None is its documented way of opting out:
    # ImportExportMixinBase.init_change_list_template() then falls back to
    # the template set above. Unused when import-export is not installed.
    import_export_change_list_template = None

    def __init__(self, model, admin_site, devices=None):
        super().__init__(model, admin_site)
        self.devices = devices

    def get_list_display(self, request):
        # resolved per request instead of being a class attribute: the
        # attribute would be a snapshot taken when this module is imported,
        # which can be before another module has replaced the registration
        return ["select_device"] + list(super().get_list_display(request))

    def get_queryset(self, request):
        # MultitenantAdminMixin.get_queryset() scopes this to the
        # organizations managed by the user, independently of list_filter
        return super().get_queryset(request).filter(pk__in=self.devices)

    @admin.display(description="")
    def select_device(self, obj):
        # deliberately without a "name": these checkboxes are never
        # submitted, execute-command.js mirrors them into the hidden
        # "excluded" field of the form holding the execute button
        return format_html(
            '<input type="checkbox" class="bc-select-device" value="{}" checked>',
            obj.pk,
        )


class BatchCommandAdmin(MultitenantAdminMixin, ReadOnlyAdmin):
    execute_command_template = "admin/connection/batch_command/execute_command.html"
    # rendered through BatchCommandDeviceAdmin.change_list_template
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
    device_commands_per_page = app_settings.BATCH_COMMAND_PAGE_SIZE
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

    def _check_add_permission(self, request):
        permission = f"{self.opts.app_label}.add_{self.opts.model_name}"
        if not request.user.has_perm(permission):
            raise PermissionDenied

    def execute_command_view(self, request):
        """First step of the mass command workflow: collect the details.

        A valid submission is stored in the session and the user is
        redirected to the confirm page (Post/Redirect/Get), so that the
        device table there can be paginated with ordinary GET requests: a
        pagination link cannot carry the contents of a form.
        """
        self._check_add_permission(request)
        if request.method == "POST":
            form = BatchCommandExecutionForm(request.POST, request=request)
            if form.is_valid():
                request.session[self.session_key] = form.to_session()
                return redirect(
                    f"admin:{self.opts.app_label}_{self.opts.model_name}_confirm"
                )
        else:
            form = BatchCommandExecutionForm(request=request)
        context = {
            **self.admin_site.each_context(request),
            "title": _("Execute mass command"),
            "opts": self.opts,
            "form": form,
            # not combined with self.media: ModelAdmin.media loads
            # jquery.init.js before select2, the opposite of what select2
            # needs (see BatchCommandExecutionForm.Media)
            "media": form.media,
            "has_view_permission": self.has_view_permission(request),
        }
        return TemplateResponse(request, self.execute_command_template, context)

    def confirm_command_view(self, request):
        """Second step: review the targeted devices and dispatch the command.

        Dispatching is decided by the HTTP method alone, never by looking
        for a field in the request body.
        """
        self._check_add_permission(request)
        if request.method == "POST":
            return self._execute_batch_command(request)
        wizard = request.session.get(self.session_key)
        if not wizard:
            return self._restart(request)
        devices = self._resolve_target_queryset(request, wizard)
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

        Composed with the ModelAdmin currently registered for Device instead
        of a named class, so that the table shows the columns of the device
        changelist as it actually is. Modules layered on top of the
        controller replace that registration rather than extending the class
        this module imports: openwisp-monitoring, for one, unregisters Device
        and registers a subclass adding the health status column.

        Resolved here, per request, rather than at import time: every app has
        finished loading by now, so the registration is final. Nothing is
        imported from those modules and none of them needs to know about this
        page; with none of them installed this returns the controller's own
        Device admin and the table is unchanged.
        """
        Device = swapper.load_model("config", "Device")
        registered = self.admin_site.get_model_admin(Device).__class__
        # the mixin comes first so that its attributes win over the
        # registered admin's
        device_admin_class = type(
            "BatchCommandDeviceAdmin",
            (BatchCommandDeviceAdminMixin, registered),
            {},
        )
        return device_admin_class(Device, self.admin_site, devices=devices)

    def get_device_changelist_template(self):
        """The template the registered Device admin renders its changelist with.

        The confirm page extends it instead of the stock changelist template,
        because that is where other modules load the assets their columns
        need: openwisp-monitoring pulls in the stylesheet drawing the health
        status accordion, and the script expanding it, from there.

        Read from the class rather than from an instance, since
        django-import-export rewrites the attribute on the instance.
        """
        Device = swapper.load_model("config", "Device")
        registered = self.admin_site.get_model_admin(Device).__class__
        return getattr(registered, "change_list_template", None) or (
            "admin/change_list.html"
        )

    def _restart(self, request):
        """Sends the user back to step one when there is no wizard to show."""
        messages.warning(
            request, _("Please fill in the mass command details to continue.")
        )
        return redirect(f"admin:{self.opts.app_label}_{self.opts.model_name}_execute")

    def _resolve_target_queryset(self, request, wizard):
        """Devices matched by the organization, group and location chosen.

        ``distinct()`` and an explicit ordering are required because this
        queryset is paginated: the devicelocation join can return the same
        device more than once, and page boundaries are undefined without an
        ordering.
        """
        Device = swapper.load_model("config", "Device")
        qs = Device.objects.all()
        if not request.user.is_superuser:
            qs = qs.filter(organization_id__in=request.user.organizations_managed)
        if wizard.get("organization_id"):
            qs = qs.filter(organization_id=wizard["organization_id"])
        if wizard.get("group_id"):
            qs = qs.filter(group_id=wizard["group_id"])
        if wizard.get("location_id"):
            qs = qs.filter(devicelocation__location_id=wizard["location_id"])
        return qs.distinct().order_by("name")

    def _confirm_context(self, request, wizard, devices):
        targets = []
        for app_label, model_name, key in (
            ("openwisp_users", "Organization", "organization_id"),
            ("config", "DeviceGroup", "group_id"),
            ("geo", "Location", "location_id"),
        ):
            if not wizard.get(key):
                continue
            model = swapper.load_model(app_label, model_name)
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
            "command_description": (wizard.get("input") or {}).get("command", ""),
            "targets_display": ", ".join(targets) if targets else _("All devices"),
            "device_count": devices.count(),
            "has_view_permission": self.has_view_permission(request),
        }

    def _execute_batch_command(self, request):
        """Applies the device selection and dispatches the mass command.

        The wizard is popped from the session before anything else happens,
        so that a double submit cannot create the batch twice: the second
        request finds nothing and is sent back to step one.
        """
        wizard = request.session.pop(self.session_key, None)
        if not wizard:
            return self._restart(request)
        devices = self._resolve_target_queryset(request, wizard)
        # The confirm page only lists the devices matched on the execute
        # page, so the selection can only ever remove from that set: the
        # browser never supplies a device to add.
        excluded = self._get_pk_list(request.POST, "excluded")
        selection = devices.exclude(pk__in=excluded)
        kwargs = {
            "type": wizard["type"],
            "label": wizard["label"],
            "input": wizard.get("input"),
            "notes": wizard.get("notes") or "",
            "organization_id": wizard.get("organization_id"),
            "group_id": wizard.get("group_id"),
            "location_id": wizard.get("location_id"),
            "devices": list(selection.distinct()),
        }
        try:
            batch = BatchCommand.execute(**kwargs)
        except ValidationError as error:
            # put the wizard back so the user can correct the selection
            request.session[self.session_key] = wizard
            messages.error(request, error.messages[0])
            return redirect(
                f"admin:{self.opts.app_label}_{self.opts.model_name}_confirm"
            )
        messages.success(request, _("Mass command executed successfully."))
        return redirect(
            f"admin:{self.opts.app_label}_{self.opts.model_name}_change", batch.pk
        )

    @staticmethod
    def _get_pk_list(source, name):
        return [pk for pk in source.get(name, "").split(",") if pk]

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

    @staticmethod
    def _command_row(command):
        return {
            "device_name": command.device.name,
            "device_pk": command.device.pk,
            "status": command.status,
            "status_display": command.get_status_display(),
            "output": (command.output or "").lstrip(),
            "created": command.created,
            "is_skipped": False,
        }

    def _paginate_commands(self, commands_qs, skipped_rows, page_param, per_page=None):
        """Returns one page of rows without loading the whole batch in memory.

        Commands keep the ordering of ``AbstractCommand.Meta`` ("created"),
        which is the order they were fanned out in: the newest one is always
        last. That is what lets the change page append results live without
        re-fetching, because a new result always belongs on the last page.

        Skipped devices are not Command rows, they are entries of the
        ``skipped_devices`` field, so they are kept as a (normally short)
        list and follow the commands.
        """
        per_page = per_page or self.device_commands_per_page
        commands_count = commands_qs.count()
        total = commands_count + len(skipped_rows)
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
        rows += skipped_rows[skipped_start:skipped_end]
        return page_obj, paginator, rows

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
            skipped_rows = []
            if obj.skipped_devices and filters["status"] in ("", "skipped"):
                skipped_rows = self._get_matching_skipped_devices(obj, filters)
            page_obj, paginator, commands = self._paginate_commands(
                commands_qs, skipped_rows, request.GET.get("page", 1)
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
                        request.GET.get(param) for param in ["status"]
                    ),
                }
            )
        return super().change_view(request, object_id, extra_context=extra_context)


admin.site.register(BatchCommand, BatchCommandAdmin)
