import os

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from openwisp_controller.config.api.urls import get_api_urls as get_config_api_urls
from openwisp_controller.config.utils import get_controller_urls
from openwisp_controller.connection.api.urls import (
    get_api_urls as get_connection_api_urls,
)
from openwisp_controller.geo.utils import get_geo_urls

from .sample_config import views as config_views
from .sample_config.api import views as config_api_views
from .sample_connection.api import views as connection_api_views
from .sample_geo import views as geo_views

redirect_view = RedirectView.as_view(url=reverse_lazy('admin:index'))

urlpatterns = []

if os.environ.get('SAMPLE_APP', False):
    urlpatterns += [
        path(
            'controller/',
            include(
                (get_controller_urls(config_views), 'controller'),
                namespace='controller',
            ),
        ),
        path(
            '',
            include(('openwisp_controller.config.urls', 'config'), namespace='config'),
        ),
        path(
            'geo/', include((get_geo_urls(geo_views), 'geo_api'), namespace='geo_api')
        ),
        path(
            'api/v1/',
            include(
                (get_config_api_urls(config_api_views), 'config_api'),
                namespace='config_api',
            ),
        ),
        path(
            'api/v1/',
            include(
                (
                    get_connection_api_urls(connection_api_views),
                    'connection_api',
                ),
                namespace='connection_api',
            ),
        ),
    ]

urlpatterns += [
    path('', redirect_view, name='index'),
    path('admin/', admin.site.urls),
    path('', include('openwisp_controller.urls')),
    path('accounts/', include('openwisp_users.accounts.urls')),
    path('api/v1/', include('openwisp_utils.api.urls')),
    path('api/v1/', include(('openwisp_users.api.urls', 'users'), namespace='users')),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns += [path('__debug__/', include(debug_toolbar.urls))]
