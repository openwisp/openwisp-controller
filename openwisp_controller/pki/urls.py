from django.conf.urls import url

from . import views

app_name = 'openwisp_controller'

urlpatterns = [
    url(r'^x509/ca/(?P<pk>[^/]+).crl$', views.crl, name='crl'),
]
