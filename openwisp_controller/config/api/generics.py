from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_netjsonconfig.api.generics import BaseListTemplateView
from django_netjsonconfig.utils import get_remote_template_data
from rest_framework.mixins import CreateModelMixin
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from ..utils import get_serializer_object


class BaseListCreateTemplateView(CreateModelMixin, BaseListTemplateView):
    """
    API used to create external template.
    This API will be used at the template library
    backend repo
    """
    permission_classes = (IsAuthenticatedOrReadOnly,)
    allowed_methods = ('GET', 'POST', 'HEAD', 'OPTION')

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        import_url = request.data.get('import-url', None)
        data = get_remote_template_data(import_url)
        try:
            try:
                template_org = self.org_model.objects.get(name=data['organization']['name'])
                org_user = self.org_user_model.objects.get(organization=template_org)
                if org_user.user == request.user:
                    self.org_model.objects.filter(pk=template_org.pk).update(**data['organization'])
                else:
                    raise ValidationError(
                        {'Organization': _('A User with this organization name already exist')}
                    )
            except self.org_model.DoesNotExist:
                template_org = self.org_model(**data['organization'])
                template_org.full_clean()
                template_org.save()
                template_org.add_user(self.request.user)
                template_org.save()
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
                'template_errors': str(e.messages)
            }
            return Response(data=errors, status=500)
        success = {
            'template_success': "Your template was successfully created"
        }
        self.template_subscription_model.subscribe(request, template)
        return Response(data=success, status=200)
