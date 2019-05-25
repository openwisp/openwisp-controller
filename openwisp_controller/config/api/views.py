from ...config.models import Template
from .generics import BaseGetTemplateView


class SharedTemplate(BaseGetTemplateView):
    template_model = Template
    queryset = Template.objects.none()


share_template = SharedTemplate.as_view()
