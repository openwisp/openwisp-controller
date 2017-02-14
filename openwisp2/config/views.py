from django.http import HttpResponse, JsonResponse

from django_netjsonconfig.utils import get_object_or_404
from openwisp2.users.models import Organization

from .models import Template


def get_default_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    user = request.user
    if not user.is_authenticated() and not user.is_staff:
        return HttpResponse(status=403)
    org = get_object_or_404(Organization, pk=organization_id)
    templates = Template.objects.filter(default=True, organization=org).only('id')
    uuids = [str(t.pk) for t in templates]
    return JsonResponse({'default_templates': uuids})
