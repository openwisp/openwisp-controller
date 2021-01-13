import json
from copy import deepcopy
from uuid import UUID

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.module_loading import import_string
from django.utils.translation import ugettext as _
from django.views.decorators.http import last_modified
from swapper import load_model

from openwisp_users.models import Organization

from .settings import BACKENDS, VPN_BACKENDS
from .utils import get_default_templates_queryset, get_object_or_404

Template = load_model('config', 'Template')


def get_default_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    backend = request.GET.get("backend", None)
    user = request.user
    authenticated = user.is_authenticated
    if not authenticated and not user.is_staff:
        return HttpResponse(status=403)
    org = get_object_or_404(Organization, pk=organization_id, is_active=True)
    templates = get_default_templates_queryset(org.pk, backend, model=Template).only(
        'id'
    )
    uuids = [str(t.pk) for t in templates]
    return JsonResponse({'default_templates': uuids})


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
    values = Template.objects.filter(pk__in=pk_list).values_list(
        'default_values', flat=True
    )
    default_values = {}
    for item in values:
        default_values.update(item)
    return JsonResponse({'default_values': default_values})
