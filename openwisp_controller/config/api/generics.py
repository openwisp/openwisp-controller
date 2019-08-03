from django.core.exceptions import ValidationError
from django_netjsonconfig.api.generics import BaseListTemplateView
from django_netjsonconfig.utils import get_remote_template_data
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from openwisp_users.models import Organization

from ..utils import get_serializer_object


class BaseListCreateTemplateView(CreateModelMixin, BaseListTemplateView):
    """
    API used to create external template.
    This API will be used at the template library
    backend repo
    """
    authentication_classes = (SessionAuthentication, BasicAuthentication)
    permission_classes = (IsAuthenticatedOrReadOnly,)
    allowed_methods = ('GET', 'POST', 'HEAD', 'OPTION')

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        import_url = request.POST.get('import-url', None)
        org = request.POST.get('org', None)
        template_org = get_object_or_404(Organization, name=org, users=self.request.user)
        data = get_remote_template_data(import_url)
        try:
            data['organization'] = template_org
            if data['type'] == 'vpn':
                data['vpn']['ca']['organization'] = template_org
                data['vpn']['cert']['organization'] = template_org
                data['vpn']['organization'] = template_org
                ca = get_serializer_object(self.request.user,
                                           self.ca_serializer,
                                           self.ca_model,
                                           data['vpn']['ca'])
                data['vpn']['ca'] = ca
                data['vpn']['cert']['ca'] = ca
                data['vpn']['cert'] = get_serializer_object(self.request.user,
                                                            self.cert_serializer,
                                                            self.cert_model,
                                                            data['vpn']['cert'])
                data['vpn'] = get_serializer_object(self.request.user,
                                                    self.vpn_serializer,
                                                    self.vpn_model, data['vpn'])
            tags = data.pop('tags')
            template = get_serializer_object(self.request.user,
                                             self.template_serializer,
                                             self.template_model,
                                             data)
            template.tags.set(*tags)
            template.url = import_url
            template.save()
        except ValidationError as e:
            errors = {
                'template-errors': str(e.messages)
            }
            return Response(data=errors, status=500)
        success = {
            'template-success': 'template {0} was successfully created'.format(template)
        }
        self.template_subscription_model.subscribe(request, template)
        return Response(data=success, status=200)
