import json

from swapper import load_model

from ...config.base.channels_consumer import BaseDeviceConsumer

Device = load_model('config', 'Device')


class CommandConsumer(BaseDeviceConsumer):
    def send_update(self, event):
        event.pop('type')
        self.send(json.dumps(event))
