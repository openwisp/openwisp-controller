import json
import uuid

from django.core.exceptions import ObjectDoesNotExist
from import_export import resources, widgets
from import_export.fields import Field
from swapper import load_model

from . import settings as app_settings

Device = load_model('config', 'Device')
Config = load_model('config', 'Config')
Template = load_model('config', 'Template')


class ManyToManyWidget(widgets.ManyToManyWidget):
    """
    https://github.com/django-import-export/django-import-export/issues/1788
    """

    def clean(self, value, row=None, **kwargs):
        cleaned = list(super().clean(value, row=None, **kwargs))
        return cleaned or ''


class DeviceResource(resources.ModelResource):
    organization = Field(
        attribute='organization__name', column_name='organization', readonly=True
    )
    group = Field(attribute='group__name', column_name='group', readonly=True)
    # readonly because config status is dynamically handled by the system
    config_status = Field(
        attribute='config__status', column_name='config_status', readonly=True
    )
    config_backend = Field(
        attribute='config__backend',
        column_name='config_backend',
        default=None,
        saves_null_values=False,
    )
    config_data = Field(
        attribute='config__config',
        column_name='config_data',
        default=None,
        saves_null_values=False,
    )
    config_context = Field(
        attribute='config__context',
        column_name='config_context',
        default=None,
        saves_null_values=False,
    )
    config_templates = Field(
        attribute='config__templates',
        column_name='config_templates',
        widget=ManyToManyWidget(Template, field='pk', separator=','),
        default=None,
        saves_null_values=False,
    )
    organization_id = Field(
        attribute='organization_id',
        column_name='organization_id',
        default=None,
        saves_null_values=False,
    )
    group_id = Field(
        attribute='group_id',
        column_name='group_id',
        default=None,
        saves_null_values=False,
    )

    def dehydrate_config_data(self, device):
        """returns JSON instead of OrderedDict representation"""
        try:
            return json.dumps(device.config.config, sort_keys=True)
        except ObjectDoesNotExist:
            pass

    def dehydrate_config_context(self, device):
        """returns JSON instead of OrderedDict representation"""
        try:
            return json.dumps(device.config.context, sort_keys=True)
        except ObjectDoesNotExist:
            pass

    def before_import_row(self, row, **kwargs):
        if 'id' in row:
            row['id'] = uuid.UUID(row['id'])
        # if JSON is invalid this line will fail
        # but will be catched by the import-export app
        if row.get('config_data'):
            row['config_data'] = json.loads(row['config_data'])
        if row.get('config_context'):
            row['config_context'] = json.loads(row['config_context'])
            if not row['config_context']:
                row['config_context'] = {}

    def get_or_init_instance(self, instance_loader, row):
        instance, new = super().get_or_init_instance(instance_loader, row)
        self._after_init_instance(instance, new, row)
        return instance, new

    def _row_has_config_data(self, row):
        """
        Returns True if dict row has at
        least one valid config attribute
        """
        return any(row.get(attr) for attr in self.Meta.config_fields)

    def _after_init_instance(self, instance, new, row):
        # initialize empty Config instance to allow
        # deeper level code to set attributes to it
        if self._row_has_config_data(row) and not instance._has_config():
            instance.config = Config()

    def validate_instance(
        self, instance, import_validation_errors=None, validate_unique=True
    ):
        super().validate_instance(
            instance, import_validation_errors=None, validate_unique=True
        )
        if not instance._has_config():
            return
        config = instance.config
        # make sure device_id on config instance is set correctly
        if config.device_id != instance.id:
            config.device_id = instance.id

    def after_save_instance(self, instance, using_transactions, dry_run):
        super().after_save_instance(instance, using_transactions, dry_run)
        if not dry_run:
            # save config afte device has been imported
            if instance._has_config():
                instance.config.save()

    class Meta:
        model = Device
        config_fields = [
            'config_status',
            'config_backend',
            'config_data',
            'config_context',
            'config_templates',
        ]
        fields = (
            [
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
            ]
            + config_fields
            + [
                'created',
                'modified',
                'id',
                'key',
                'organization_id',
                'group_id',
            ]
        )
        if app_settings.HARDWARE_ID_ENABLED:
            fields.insert(1, 'hardware_id')
        export_order = fields
