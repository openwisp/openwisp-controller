import json
from copy import deepcopy
from uuid import UUID

from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import gettext as _
from django.views.decorators.http import last_modified
from swapper import load_model

from .settings import BACKENDS, VPN_BACKENDS
from .utils import get_object_or_404

Organization = load_model('openwisp_users', 'Organization')
Template = load_model('config', 'Template')


def get_relevant_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    backend = request.GET.get("backend", None)
    user = request.user
    if not user.is_superuser and not user.is_manager(organization_id):
        return HttpResponse(status=403)
    org = get_object_or_404(Organization, pk=organization_id, is_active=True)
    queryset = (
        Template.objects.filter(backend=backend)
        .filter(Q(organization_id=org.pk) | Q(organization_id=None))
        .values('id', 'required', 'default', 'name')
    )
    relevant_templates = {}
    for template in queryset:
        relevant_templates[str(template.pop('id'))] = template
    return JsonResponse(relevant_templates)


ALL_BACKENDS = BACKENDS + VPN_BACKENDS

# ``available_schemas`` and ``available_schemas_json``
# will be generated only once at startup
available_schemas = {}
for backend_path, label in ALL_BACKENDS:  # noqa
    backend = import_string(backend_path)
    schema = deepcopy(backend.schema)
    # must use conditional because some custom backends might not specify an hostname
    if 'general' in schema['properties']:
        # hide hostname because it's handled via models
        if 'hostname' in schema['properties']['general']['properties']:
            del schema['properties']['general']['properties']['hostname']
        # remove hosname from required properties
        if 'hostname' in schema['properties']['general'].get('required', []):
            del schema['properties']['general']['required']
    # start editor empty by default, except for VPN schemas
    if (backend_path, label) not in VPN_BACKENDS:
        schema['defaultProperties'] = []
    available_schemas[backend_path] = schema
available_schemas_json = json.dumps(available_schemas)

login_required_error = json.dumps({'error': _('login required')})

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
    return HttpResponse(c, status=status, content_type='application/json')


def get_template_default_values(request):
    """
    returns default_values for one or more templates
    """
    user = request.user
    pk_list = []
    for pk in request.GET.get('pks', '').split(','):
        try:
            UUID(pk, version=4)
        except ValueError:
            return JsonResponse(
                {'error': 'invalid template pks were received'}, status=400
            )
        else:
            pk_list.append(pk)
    where = Q(pk__in=pk_list)
    if not user.is_superuser:
        where = where & (
            Q(organization=None) | Q(organization__in=user.organizations_managed)
        )
    qs = Template.objects.filter(where).values('id', 'default_values')
    qs_dict = {}
    # Create a mapping of UUID to default values of the templates in qs_dict.
    # Iterate over received pk_list and retrieve default_values for corresponding
    # template from qs_dict.
    # This ensures that default_values of templates that come later in the order
    # will override default_values of any previous template if same keys are present.
    for template in qs:
        qs_dict[str(template['id'])] = template['default_values']
    default_values = {}
    for pk in pk_list:
        default_values.update(qs_dict[pk])
    return JsonResponse({'default_values': default_values})
