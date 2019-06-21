from django_netjsonconfig.api.generics import BaseListTemplateView, BaseTemplateDetailView

from ..models import Template


class TemplateDetailView(BaseTemplateDetailView):
    template_model = Template


class ListTemplateView(BaseListTemplateView):

    def get_queryset(self):
        """
        If organization is given, return templates belonging to that
        organization to super() queryset otherwise return an empty
        queryset.
        """
        org = self.request.GET.get('org', None)
        if org:
            self.queryset = Template.objects.filter(organization=org)
            return super(ListTemplateView, self).get_queryset()
        else:
            qs = self.template_model.objects.none()
            return qs


template_detail = TemplateDetailView.as_view()
list_template = ListTemplateView.as_view()
