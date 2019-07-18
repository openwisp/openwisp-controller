from django.core.exceptions import ValidationError
from django_netjsonconfig.tasks import subscribe
from django_netjsonconfig.utils import get_remote_template_data
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListCreateAPIView, get_object_or_404
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from openwisp_users.models import Organization


class BaseListCreateTemplateView(ListCreateAPIView):
    """
    API used to create external template.
    This API will be used at the template library
    backend repo
    """
    authentication_classes = (SessionAuthentication,)
    permission_classes = (DjangoModelPermissions,)

    def get_queryset(self):
        orgs = Organization.objects.filter(users=self.request.user)
        templates = self.template_model.objects.filter(organization__in=orgs)
        return templates

    def post(self, request, *args, **kwargs):
        import_url = request.POST.get('import-url', None)
        data = get_remote_template_data(import_url)
        org = request.POST.get('org', None)
        template_org = get_object_or_404(Organization, name=org, users=self.request.user)
        data['organization'] = template_org
        if data['type'] == 'vpn':
            data['vpn']['ca']['organization'] = template_org
            data['vpn']['cert']['organization'] = template_org
            data['vpn']['organization'] = template_org
        self.serializer_class.user_orgs = Organization.objects.filter(users=self.request.user)
        serialized_data = self.serializer_class(data=data)
        if serialized_data.is_valid():
            try:
                serialized_data.save()
                success = {
                    'template-success': 'Template was successfully created'
                }
                subscriber_url = '{0}://{1}'.format(request.META.get('wsgi.url_scheme'),
                                                    request.get_host())
                subscribe.delay(data['id'], import_url, subscriber_url, subscribe=True)
                return Response(data=success, status=200)
            except ValidationError as e:
                error = {
                    'template-error': str(e.messages)
                }
                return Response(data=error, status=500)
        else:
            return Response(data=serialized_data.errors, status=500)
