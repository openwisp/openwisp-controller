from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class UsersConfig(AppConfig):
    name = 'openwisp2.users'
    app_label = 'users'
    verbose_name = _('Users and Organizations')
