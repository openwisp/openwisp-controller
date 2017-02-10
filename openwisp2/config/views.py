from django.http import HttpResponse, JsonResponse

from openwisp2.orgs.models import Organization

from .models import Template


def get_default_templates(request, organization_id):
    """
    returns default templates of specified organization
    """
    user = request.user
    if not user.is_authenticated() and not user.is_staff:
        return HttpResponse(status=403)
    try:
        org = Organization.objects.get(pk=organization_id)
    except Organization.DoesNotExist:
        return HttpResponse(status=404)
    except ValueError:
        return HttpResponse(status=400)
    templates = Template.objects.filter(default=True, organization=org).only('id')
    uuids = [str(t.pk) for t in templates]
    return JsonResponse({'default_templates': uuids})
