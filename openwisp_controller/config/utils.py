from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from openwisp_users.models import OrganizationUser


def get_default_templates_queryset(organization_id, queryset=None, model=None):
    """
    Adds organization filtering to default template queryset:
        filter only templates belonging to same organization
        or shared templates (with organization=None)
    This function is used in:
        * openwisp_controller.config.Template.get_default_templates
        * openwisp_controller.config.views.get_default_templates
    """
    if queryset is None:
        queryset = model.objects.filter(default=True)
    queryset = queryset.filter(Q(organization_id=organization_id) |
                               Q(organization_id=None))
    return queryset


def get_serializer_object(user, serializer, model, data):
    serializer.Meta.model = model
    serializer.model = model
    serializer_data = serializer(data=data)
    if serializer_data.is_valid():
        return serializer_data.save()
    else:
        if str(model.__name__) in ["Ca", "Cert", "Vpn"]:
            obj_name = data['name']
            obj = model.objects.get(name=obj_name)
            obj_org_user = OrganizationUser.objects.get(organization=obj.organization)
            if obj_org_user.user == user:
                model.objects.filter(name=obj_name).update(**data)
                return model.objects.get(name=obj_name)
            else:
                raise ValidationError(_("{0}".format(serializer_data.errors)))
        raise ValidationError(_("{0}".format(serializer_data.errors)))
