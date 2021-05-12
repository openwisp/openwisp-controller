from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ugettext_lazy as _
from django_x509.settings import CRL_PROTECTED
from rest_framework import pagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged

from .serializers import (
    CaDetailSerializer,
    CaListSerializer,
    CertDetailSerializer,
    CertListSerializer,
)

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProtectedAPIMixin(FilterByOrganizationManaged):
    authentication_classes = [BearerAuthentication, SessionAuthentication]
    permission_classes = [
        IsAuthenticated,
        DjangoModelPermissions,
    ]


class CaListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = CaListSerializer
    queryset = Ca.objects.order_by('-created')
    pagination_class = ListViewPagination


class CaDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = CaDetailSerializer
    queryset = Ca.objects.all()


def crl_download_view(request, pk):
    authenticated = request.user.is_authenticated
    if CRL_PROTECTED or not authenticated:
        return HttpResponse(_('Forbidden'), status=403, content_type='text/plain')
    instance = get_object_or_404(Ca, pk=pk)
    response = HttpResponse(
        instance.crl, status=200, content_type='application/x-pem-file'
    )
    response['Content-Disposition'] = f'attachment; filename={pk}.crl'
    return response


class CertListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = CertListSerializer
    queryset = Cert.objects.order_by('-created')
    pagination_class = ListViewPagination


class CertDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = CertDetailSerializer
    queryset = Cert.objects.all()


ca_list = CaListCreateView.as_view()
ca_detail = CaDetailView.as_view()
cert_list = CertListCreateView.as_view()
cert_detail = CertDetailView.as_view()
