from django.conf.urls import include, url

urlpatterns = [
    url(r'', include('openwisp2.ui.urls', namespace='ui', app_name='ui')),
]
