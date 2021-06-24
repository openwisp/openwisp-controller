from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import pagination
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import (
    CreateAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from swapper import load_model

from openwisp_users.api.authentication import BearerAuthentication
from openwisp_users.api.mixins import FilterByOrganizationManaged

from .serializers import (
    CaDetailSerializer,
    CaImportSerializer,
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


class CrlDownloadView(ProtectedAPIMixin, RetrieveAPIView):
    serializer_class = CaDetailSerializer
    queryset = Ca.objects.none()

    def retrieve(self, request, *args, **kwargs):
        instance = get_object_or_404(Ca, pk=kwargs['pk'])
        return HttpResponse(
            instance.crl, status=200, content_type='application/x-pem-file'
        )


class CertListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = CertListSerializer
    queryset = Cert.objects.order_by('-created')
    pagination_class = ListViewPagination


class CertDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = CertDetailSerializer
    queryset = Cert.objects.all()


class ImportExistingCaView(ProtectedAPIMixin, CreateAPIView):
    serializer_class = CaImportSerializer
    queryset = Ca.objects.all()


ca_list = CaListCreateView.as_view()
ca_detail = CaDetailView.as_view()
cert_list = CertListCreateView.as_view()
cert_detail = CertDetailView.as_view()
crl_download = CrlDownloadView.as_view()
import_existing_ca = ImportExistingCaView.as_view()
