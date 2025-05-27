import json
from collections import OrderedDict
from copy import deepcopy
from uuid import UUID

from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from django.views.decorators.http import last_modified
from swapper import load_model

from .settings import BACKENDS, VPN_BACKENDS

Organization = load_model("openwisp_users", "Organization")
Template = load_model("config", "Template")
Config = load_model("config", "Config")
DeviceGroup = load_model("config", "DeviceGroup")
OrganizationConfigSettings = load_model("config", "OrganizationConfigSettings")


def get_relevant_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    backend = request.GET.get("backend", None)
    device_id = request.GET.get("device_id", None)
    group_id = request.GET.get("group_id", None)
    user = request.user
    # organization_id is passed as 'null' for add device
    organization_id = None if organization_id == "null" else organization_id
    if (
        not user.is_superuser
        and organization_id
        and not user.is_manager(organization_id)
    ):
        return HttpResponse(status=403)

    if organization_id:
        # return 400 if organization_id is not a valid UUID
        try:
            organization_id = UUID(organization_id, version=4)
        except ValueError:
            return HttpResponseBadRequest(_(f"{organization_id} is not a valid UUID."))
        if not Organization.objects.filter(pk=organization_id, is_active=True).exists():
            raise Http404(_("Organization does not exist."))
        org_filters = Q(organization_id=organization_id)
    # if the user is superuser then we need to fetch all the templates
    elif user.is_superuser:
        org_filters = Q(organization_id__isnull=False)
    # else fetch templates of organizations managed by the user
    else:
        org_filters = Q(organization_id__in=user.organizations_managed)

    # this filter is for shared templates
    org_filters |= Q(organization_id=None)

    filter_options = {}
    if backend:
        filter_options.update(backend=backend)
    else:
        filter_options.update(required=False, default=False)

    queryset = (
        Template.objects.filter(**filter_options)
        .filter(org_filters)
        .only("id", "name", "backend", "default", "required")
    )
    selected_templates = []
    if device_id:
        selected_templates = (
            Config.objects.prefetch_related("templates")
            .only("templates")
            .get(device_id=device_id)
            .templates.all()
        )
    if group_id:
        selected_templates = (
            DeviceGroup.objects.prefetch_related("templates")
            .only("templates")
            .get(pk=group_id)
            .templates.filter(organization_id=organization_id)
        )

    relevant_templates = OrderedDict()
    for template in selected_templates:
        relevant_templates[str(template.pk)] = dict(
            name=template.name,
            backend=template.get_backend_display(),
            default=template.default,
            required=template.required,
            selected=True,
        )

    for template in queryset.exclude(pk__in=relevant_templates.keys()):
        relevant_templates[str(template.pk)] = dict(
            name=template.name,
            backend=template.get_backend_display(),
            default=template.default,
            required=template.required,
            selected=False,
        )

    return JsonResponse(relevant_templates)


ALL_BACKENDS = BACKENDS + VPN_BACKENDS

# ``available_schemas`` and ``available_schemas_json``
# will be generated only once at startup
available_schemas = {}
for backend_path, label in ALL_BACKENDS:  # noqa
    backend = import_string(backend_path)
    schema = deepcopy(backend.schema)
    # must use conditional because some custom backends might not specify an hostname
    if "general" in schema["properties"]:
        # hide hostname because it's handled via models
        if "hostname" in schema["properties"]["general"]["properties"]:
            del schema["properties"]["general"]["properties"]["hostname"]
        # remove hosname from required properties
        if "hostname" in schema["properties"]["general"].get("required", []):
            del schema["properties"]["general"]["required"]
    # start editor empty by default, except for VPN schemas
    if (backend_path, label) not in VPN_BACKENDS:
        schema["defaultProperties"] = []
    available_schemas[backend_path] = schema
available_schemas_json = json.dumps(available_schemas)

login_required_error = json.dumps({"error": _("login required")})

# ``start_time`` will contain the datetime of the moment in which the
# application server is started and it is used in the last-modified
# header of the HTTP response of ``schema`` view
start_time = timezone.now()


@last_modified(lambda request: start_time)
def schema(request):
    """
    returns configuration checksum
    """
    authenticated = request.user.is_authenticated
    if authenticated:
        c = available_schemas_json
        status = 200
    else:
        c = login_required_error
        status = 403
    return HttpResponse(c, status=status, content_type="application/json")


def get_default_values(request):
    """
    The view returns default values from the templates, group,
    and organization specified in the URL's query parameters.

    URL query parameters:
        pks (required): Comma separated primary keys of Template
        group (optional): Primary key of the DeviceGroup
        organization (optional): Primary key of the Organization

    The conflicting keys between the templates' default_values,
    DeviceGroup's context and Organization's context are overridden
    by the value present according to following precedence (highest to lowest):
        1. DeviceGroup context
        2. Organization context
        3. Template default_values

    NOTE: Not all key-value pair of
    DeviceGroup.context / Organization.config_setting.context are added
    in the response. Only the conflicting keys are altered.
    """

    def _clean_pk(pks):
        pk_list = []
        for pk in pks:
            UUID(pk, version=4)
            pk_list.append(pk)
        return pk_list

    def _update_default_values(model, model_where, default_values):
        try:
            instance = model.objects.only("context").get(model_where)
        except model.DoesNotExist:
            pass
        else:
            for key, value in instance.get_context().items():
                if key in default_values:
                    default_values[key] = value

    user = request.user
    try:
        templates_pk_list = _clean_pk(request.GET.get("pks", "").split(","))
    except ValueError:
        return JsonResponse({"error": "invalid template pks were received"}, status=400)
    group_pk = request.GET.get("group", None)
    organization_pk = request.GET.get("organization", None)
    if group_pk:
        try:
            group_pk = _clean_pk([group_pk])[0]
        except ValueError:
            return JsonResponse({"error": "invalid group pk was received"}, status=400)
        else:
            group_where = Q(pk=group_pk)
            if not request.user.is_superuser:
                group_where &= Q(organization__in=user.organizations_managed)
    if organization_pk:
        try:
            organization_pk = _clean_pk([organization_pk])[0]
        except ValueError:
            return JsonResponse(
                {"error": "invalid organization pk was received"}, status=400
            )
        else:
            config_settings_where = Q(organization_id=organization_pk)
            if not request.user.is_superuser:
                config_settings_where &= Q(organization__in=user.organizations_managed)

    templates_where = Q(pk__in=templates_pk_list)
    if not user.is_superuser:
        templates_where = templates_where & (
            Q(organization=None) | Q(organization__in=user.organizations_managed)
        )
    templates_qs = Template.objects.filter(templates_where).values(
        "id", "default_values"
    )
    templates_qs_dict = {}
    # Create a mapping of UUID to default values of the templates in templates_
    # qs_dict. Iterate over received templates_pk_list and retrieve default_values for
    # corresponding template from templates_qs_dict.
    # This ensures that default_values of templates that come later in the order
    # will override default_values of any previous template if same keys are present.
    for template in templates_qs:
        templates_qs_dict[str(template["id"])] = template["default_values"]
    default_values = {}
    for pk in templates_pk_list:
        default_values.update(templates_qs_dict.get(pk, {}))
    # Check for conflicting key's in OrganizationConfigSettings.context
    if organization_pk:
        _update_default_values(
            OrganizationConfigSettings, config_settings_where, default_values
        )

    # Check for conflicting key's in DeviceGroup.context
    if group_pk:
        _update_default_values(DeviceGroup, group_where, default_values)
    return JsonResponse({"default_values": default_values})
