from ..utils import get_geo_urls
from . import views as geo_views

app_name = 'openwisp_controller'

urlpatterns = get_geo_urls(geo_views)
