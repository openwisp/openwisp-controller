from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import pagination, serializers
from rest_framework.generics import (
    GenericAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.response import Response
from swapper import load_model

from ...mixins import ProtectedAPIMixin
from .serializers import (
    CaDetailSerializer,
    CaListSerializer,
    CaRenewSerializer,
    CertDetailSerializer,
    CertListSerializer,
    CertRevokeRenewSerializer,
)

Ca = load_model('django_x509', 'Ca')
Cert = load_model('django_x509', 'Cert')


class ListViewPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CaListCreateView(ProtectedAPIMixin, ListCreateAPIView):
    serializer_class = CaListSerializer
    queryset = Ca.objects.order_by('-created')
    pagination_class = ListViewPagination


class CaDetailView(ProtectedAPIMixin, RetrieveUpdateDestroyAPIView):
    serializer_class = CaDetailSerializer
    queryset = Ca.objects.all()


class CaRenewView(ProtectedAPIMixin, GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Ca.objects.all()

    def post(self, request, pk):
        """
        Renews the CA.
        """
        instance = self.get_object()
        instance.renew()
        serializer = CaRenewSerializer(instance)
        return Response(serializer.data, status=200)


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
    queryset = Cert.objects.select_related('ca')


class CertRevokeRenewBaseView(ProtectedAPIMixin, GenericAPIView):
    serializer_class = serializers.Serializer
    queryset = Cert.objects.select_related('ca')


class CertRevokeView(CertRevokeRenewBaseView):
    def post(self, request, pk):
        """
        Revokes the Certificate.
        """
        instance = self.get_object()
        instance.revoke()
        serializer = CertRevokeRenewSerializer(instance)
        return Response(serializer.data, status=200)


class CertRenewView(CertRevokeRenewBaseView):
    def post(self, request, pk):
        """
        Renews the Certificate.
        """
        instance = self.get_object()
        instance.renew()
        serializer = CertRevokeRenewSerializer(instance)
        return Response(serializer.data, status=200)


ca_list = CaListCreateView.as_view()
ca_detail = CaDetailView.as_view()
ca_renew = CaRenewView.as_view()
cert_list = CertListCreateView.as_view()
cert_detail = CertDetailView.as_view()
crl_download = CrlDownloadView.as_view()
cert_revoke = CertRevokeView.as_view()
cert_renew = CertRenewView.as_view()
