from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^x509/ca/(?P<pk>[^/]+).crl$', views.crl, name='crl'),
]
