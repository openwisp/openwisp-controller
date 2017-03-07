from django.db.models import Q


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
