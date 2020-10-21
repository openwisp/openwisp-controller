from celery.task.control import inspect
from django.apps import AppConfig
from django.db import transaction
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _
from openwisp_notifications.signals import notify
from openwisp_notifications.types import register_notification_type
from swapper import load_model

from ..config.signals import config_modified
from .signals import is_working_changed

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
        self.register_notification_types()
        config_modified.connect(
            self.config_modified_receiver, dispatch_uid='connection.update_config'
        )
        Config = load_model('config', 'Config')
        Credentials = load_model('connection', 'Credentials')
        post_save.connect(
            Credentials.auto_add_credentials_to_device,
            sender=Config,
            dispatch_uid='connection.auto_add_credentials',
        )
        is_working_changed.connect(
            self.is_working_changed_receiver,
            sender=load_model('connection', 'DeviceConnection'),
            dispatch_uid='is_working_changed_receiver',
        )

    @classmethod
    def config_modified_receiver(cls, **kwargs):
        device = kwargs['device']
        conn_count = device.deviceconnection_set.count()
        # if device has no connection specified stop here
        if conn_count < 1:
            return
        transaction.on_commit(lambda: cls._launch_update_config(device.pk))

    @classmethod
    def _launch_update_config(cls, device_pk):
        """
        Calls the background task update_config only if
        no other tasks are running for the same device
        """
        if cls._is_update_in_progress(device_pk):
            return
        from .tasks import update_config

        update_config.delay(device_pk)

    @classmethod
    def _is_update_in_progress(cls, device_pk):
        active = inspect().active()
        if not active:
            return False
        # check if there's any other running task before adding it
        for task_list in active.values():
            for task in task_list:
                if task['name'] == _TASK_NAME and str(device_pk) in task['args']:
                    return True
        return False

    @classmethod
    def is_working_changed_receiver(
        cls, instance, is_working, old_is_working, **kwargs
    ):
        # if old_is_working is None, it's a new device connection which wasn't
        # used yet, so nothing is really changing and we won't notify the user
        if old_is_working is None:
            return
        device = instance.device
        notification_opts = dict(sender=instance, target=device)
        if not is_working:
            notification_opts['type'] = 'connection_is_not_working'
        else:
            notification_opts['type'] = 'connection_is_working'
        notify.send(**notification_opts)

    def register_notification_types(self):
        register_notification_type(
            'connection_is_not_working',
            {
                'verbose_name': 'Device Connection PROBLEM',
                'verb': 'not working',
                'level': 'error',
                'email_subject': (
                    '[{site.name}] PROBLEM: Connection to '
                    'device {notification.target}'
                ),
                'message': (
                    '{notification.actor.credentials} connection to '
                    'device [{notification.target}]({notification.target_link}) '
                    'is {notification.verb}. {notification.actor.failure_reason}'
                ),
            },
        )
        register_notification_type(
            'connection_is_working',
            {
                'verbose_name': 'Device Connection RECOVERY',
                'verb': 'working',
                'level': 'info',
                'email_subject': (
                    '[{site.name}] RECOVERY: Connection to '
                    'device {notification.target}'
                ),
                'message': (
                    '{notification.actor.credentials} connection to '
                    'device [{notification.target}]({notification.target_link}) '
                    'is {notification.verb}. {notification.actor.failure_reason}'
                ),
            },
        )
