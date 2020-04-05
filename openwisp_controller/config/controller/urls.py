from ..utils import get_controller_urls
from . import views

app_name = 'openwisp_controller'
urlpatterns = get_controller_urls(views)
