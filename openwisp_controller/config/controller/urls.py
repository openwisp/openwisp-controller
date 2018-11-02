from django_netjsonconfig.utils import get_controller_urls

from . import views

urlpatterns = get_controller_urls(views)
