from django.http import HttpResponse, JsonResponse

from django_netjsonconfig.utils import get_object_or_404
from openwisp_users.models import Organization

from .models import Template
from .utils import get_default_templates_queryset


def get_default_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    user = request.user
    if not user.is_authenticated() and not user.is_staff:
        return HttpResponse(status=403)
    org = get_object_or_404(Organization, pk=organization_id, is_active=True)
    templates = get_default_templates_queryset(org.pk, model=Template).only('id')
    uuids = [str(t.pk) for t in templates]
    return JsonResponse({'default_templates': uuids})
