from ..utils import get_api_urls
from . import views as api_views

app_name = 'openwisp_controller'

urlpatterns = get_api_urls(api_views)
