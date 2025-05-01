import json
from copy import deepcopy

from swapper import load_model

from ...config.base.channels_consumer import BaseDeviceConsumer

Device = load_model('config', 'Device')


class CommandConsumer(BaseDeviceConsumer):
    def send_update(self, event):
        data = deepcopy(event)
        data.pop('type')
        self.send(json.dumps(data))
