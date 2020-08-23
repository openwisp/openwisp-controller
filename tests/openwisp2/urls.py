import os

from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import reverse_lazy
from django.views.generic import RedirectView

from openwisp_controller.config.utils import get_controller_urls
from openwisp_controller.geo.utils import get_geo_urls

from .sample_config import views as config_views
from .sample_geo import views as geo_views

redirect_view = RedirectView.as_view(url=reverse_lazy('admin:index'))

urlpatterns = []

if os.environ.get('SAMPLE_APP', False):
    urlpatterns += [
        url(
            r'^controller/',
            include(
                (get_controller_urls(config_views), 'controller'),
                namespace='controller',
            ),
        ),
        url(r'^geo/', include((get_geo_urls(geo_views), 'geo'), namespace='geo'),),
    ]

urlpatterns += [
    url(r'^$', redirect_view, name='index'),
    url(r'^admin/', admin.site.urls),
    url(r'', include('openwisp_controller.urls')),
    url(r'', include('openwisp_notifications.urls')),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [url(r'^__debug__/', include(debug_toolbar.urls))]
