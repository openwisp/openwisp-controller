from django_netjsonconfig.utils import get_api_urls
from openwisp_controller.config.api import views

app_name = 'openwisp_controller'

urlpatterns = get_api_urls(views)
