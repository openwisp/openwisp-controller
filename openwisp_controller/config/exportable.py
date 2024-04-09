import json

from django.core.exceptions import ObjectDoesNotExist
from import_export import resources, widgets
from import_export.fields import Field
from swapper import load_model

from . import settings as app_settings

Device = load_model('config', 'Device')
Config = load_model('config', 'Config')


class DeviceResource(resources.ModelResource):
    organization = Field(attribute='organization__name', column_name='organization')
    group = Field(attribute='group__name', column_name='group')
    config_status = Field(attribute='config__status', column_name='config_status')
    config_backend = Field(attribute='config__backend', column_name='config_backend')
    config_data = Field(attribute='config__config', column_name='config_data')
    config_context = Field(attribute='config__context', column_name='config_context')
    config_templates = Field(
        attribute='config__templates',
        column_name='config_templates',
        widget=widgets.ManyToManyWidget(Config, field='pk', separator=','),
    )
    organization_id = Field(attribute='organization_id', column_name='organization_id')
    group_id = Field(attribute='group_id', column_name='group_id')

    def dehydrate_config_data(self, device):
        try:
            return json.dumps(device.config.config, sort_keys=True)
        except ObjectDoesNotExist:
            pass

    def dehydrate_config_context(self, device):
        try:
            return json.dumps(device.config.context, sort_keys=True)
        except ObjectDoesNotExist:
            pass

    class Meta:
        model = Device
        fields = [
            'name',
            'mac_address',
            'organization',
            'group',
            'model',
            'os',
            'system',
            'notes',
            'last_ip',
            'management_ip',
            'config_status',
            'config_backend',
            'config_data',
            'config_context',
            'config_templates',
            'created',
            'modified',
            'id',
            'key',
            'organization_id',
            'group_id',
        ]
        if app_settings.HARDWARE_ID_ENABLED:
            fields.insert(1, 'hardware_id')
        export_order = fields
