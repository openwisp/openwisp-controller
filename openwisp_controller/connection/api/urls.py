from ..utils import get_command_urls
from . import views as command_views

app_name = 'openwisp_controller'

urlpatterns = get_command_urls(command_views)
