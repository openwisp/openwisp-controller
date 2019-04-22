from celery.task.control import inspect
from django.apps import AppConfig
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.signals import config_modified

_TASK_NAME = 'openwisp_controller.connection.tasks.update_config'


class ConnectionConfig(AppConfig):
    name = 'openwisp_controller.connection'
    label = 'connection'
    verbose_name = _('Network Device Credentials')

    def ready(self):
        """
        connects the ``config_modified`` signal
        to the ``update_config`` celery task
        which will be executed in the background
        """
        config_modified.connect(self.config_modified_receiver,
                                dispatch_uid='connection.update_config')

        from ..config.models import Config
        from .models import Credentials

        post_save.connect(Credentials.auto_add_credentials_to_device,
                          sender=Config,
                          dispatch_uid='connection.auto_add_credentials')

    @classmethod
    def config_modified_receiver(cls, **kwargs):
        from .tasks import update_config
        d = kwargs['device']
        conn_count = d.deviceconnection_set.count()
        # if device has no connection specified
        # or update is already in progress, stop here
        if conn_count < 1 or cls._is_update_in_progress(d.id):
            return
        update_config.delay(d.id)

    @classmethod
    def _is_update_in_progress(cls, device_id):
        active = inspect().active()
        if not active:
            return False
        # check if there's any other running task before adding it
        for task_list in active.values():
            for task in task_list:
                if task['name'] == _TASK_NAME and str(device_id) in task['args']:
                    return True
        return False
