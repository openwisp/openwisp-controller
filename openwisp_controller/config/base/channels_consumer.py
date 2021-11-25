from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from swapper import load_model

Device = load_model('config', 'Device')


class BaseDeviceConsumer(WebsocketConsumer):
    model = Device
    channel_layer_group = 'config.device'

    def _is_user_authenticated(self):
        try:
            assert self.scope['user'].is_authenticated is True
        except (KeyError, AssertionError):
            self.close()
            return False
        else:
            return True

    def is_user_authorized(self):
        user = self.scope['user']
        return user.is_superuser or (user.is_staff and self._user_has_permissions())

    def _user_has_permissions(self, add=True, change=True, delete=True):
        permissions = []
        model_identifier = '{0}.{1}_{2}'.format(
            self.model._meta.app_label,
            '{permission}',
            self.model._meta.model_name,
        )
        if add:
            permissions.append(model_identifier.format(permission='add'))
        if change:
            permissions.append(model_identifier.format(permission='change'))
        if delete:
            permissions.append(model_identifier.format(permission='delete'))
        return self.scope['user'].has_perms(permissions)

    def connect(self):
        try:
            assert self._is_user_authenticated() and self.is_user_authorized()
            self.pk_ = self.scope['url_route']['kwargs']['pk']
        except (AssertionError, KeyError):
            self.close()
        else:
            async_to_sync(self.channel_layer.group_add)(
                f'{self.channel_layer_group}-{self.pk_}', self.channel_name
            )
            self.accept()

    def disconnect(self, close_code):
        try:
            async_to_sync(self.channel_layer.group_discard)(
                f'{self.channel_layer_group}-{self.pk_}', self.channel_name
            )
        except AttributeError:
            # The "disconnect" method is called after the "close" method.
            # Termination of a connection which was never accepted also
            # triggers this method. "self.pk_" is only set for accepted
            # connections, therefore an error is raised during termination
            # of rejected connection requests which is handled by this block.
            return
