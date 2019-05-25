from rest_framework.generics import RetrieveAPIView, get_object_or_404
from rest_framework.response import Response

from .serializers import TemplateRetrieveSerializer


class BaseGetTemplateView(RetrieveAPIView):
    serializer_class = TemplateRetrieveSerializer

    def get(self, request, *args, **kwargs):
        key = request.GET.get('key', None)
        if key:
            temp = get_object_or_404(self.template_model, pk=kwargs['uuid'], key=key,
                                     sharing='secret_key')
        else:
            temp = get_object_or_404(self.template_model, pk=kwargs['uuid'], sharing='public')
        serializer = TemplateRetrieveSerializer(temp)
        return Response(serializer.data)
