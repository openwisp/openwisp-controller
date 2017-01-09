from django.conf.urls import include, url
from organizations.backends import invitation_backend

urlpatterns = [
    # organizations
    url(r'^accounts/', include('organizations.urls')),
    url(r'^invitations/', include(invitation_backend().get_urls())),
    # openwisp2.ui
    url(r'', include('openwisp2.ui.urls', namespace='ui', app_name='ui')),
    # django-netjsonconfig
    url(r'^', include('django_netjsonconfig.urls', namespace='netjsonconfig')),
]
