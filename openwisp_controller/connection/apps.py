from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _
from django_netjsonconfig.signals import config_modified
from celery.task.control import inspect

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
        from .tasks import update_config

        def config_modified_receiver(**kwargs):
            device_id = kwargs['device'].id
            if not self._is_update_in_progress(device_id):
                update_config.delay(device_id)

        config_modified.connect(config_modified_receiver,
                                dispatch_uid='connection.update_config',
                                weak=False)

    def _is_update_in_progress(self, device_id):
        # check if there's any other running task before adding it
        for task_list in inspect().active().values():
            for task in task_list:
                if task['name'] == _TASK_NAME and str(device_id) in task['args']:
                    return True
        return False
