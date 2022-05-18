import logging

import requests
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

from openwisp_utils.tasks import OpenwispCeleryTask

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=1200)
def update_template_related_config_status(template_pk):
    """
    Flags config objects related to the specified
    template PK as modified and triggers config
    modified and config status changed signals
    """
    Template = load_model('config', 'Template')
    try:
        template = Template.objects.get(pk=template_pk)
    except ObjectDoesNotExist as e:
        logger.warning(
            f'update_template_related_config_status("{template_pk}") failed: {e}'
        )
        return
    try:
        template._update_related_config_status()
    except SoftTimeLimitExceeded:
        logger.error(
            'soft time limit hit while executing '
            f'_update_related_config_status for {template} '
            f'(ID: {template_pk})'
        )


@shared_task(soft_time_limit=1200)
def create_vpn_dh(vpn_pk):
    """
    Generates DH parameters
    """
    Vpn = load_model('config', 'Vpn')
    vpn = Vpn.objects.get(pk=vpn_pk)
    try:
        vpn.dh = Vpn.dhparam(2048)
    except SoftTimeLimitExceeded:
        logger.error(
            'soft time limit hit while generating DH '
            f'parameters for VPN Server {vpn} (ID: {vpn_pk})'
        )
    else:
        vpn.full_clean()
        vpn.save()


@shared_task(base=OpenwispCeleryTask)
def invalidate_devicegroup_cache_change(instance_id, model_name):
    from .api.views import DeviceGroupCommonName

    Device = load_model('config', 'Device')
    DeviceGroup = load_model('config', 'DeviceGroup')
    Cert = load_model('django_x509', 'Cert')

    if model_name == Device._meta.model_name:
        DeviceGroupCommonName.device_change_invalidates_cache(instance_id)
    elif model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_change_invalidates_cache(instance_id)
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_change_invalidates_cache(instance_id)


@shared_task(base=OpenwispCeleryTask)
def invalidate_devicegroup_cache_delete(instance_id, model_name, **kwargs):
    from .api.views import DeviceGroupCommonName

    DeviceGroup = load_model('config', 'DeviceGroup')
    Cert = load_model('django_x509', 'Cert')

    if model_name == DeviceGroup._meta.model_name:
        DeviceGroupCommonName.devicegroup_delete_invalidates_cache(
            kwargs['organization_id']
        )
    elif model_name == Cert._meta.model_name:
        DeviceGroupCommonName.certificate_delete_invalidates_cache(
            kwargs['organization_id'], kwargs['common_name']
        )


@shared_task(base=OpenwispCeleryTask)
def trigger_vpn_server_endpoint(endpoint, auth_token, vpn_id):
    response = requests.post(
        endpoint,
        params={'key': auth_token},
        verify=False if getattr(settings, 'DEBUG') else True,
    )
    if response.status_code == 200:
        logger.info(f'Triggered update webhook of VPN Server UUID: {vpn_id}')
    else:
        logger.error(
            'Failed to update VPN Server configuration. '
            f'Response status code: {response.status_code}, '
            f'VPN Server UUID: {vpn_id}',
        )


@shared_task(base=OpenwispCeleryTask)
def change_devices_templates(instance_id, model_name, **kwargs):
    def filter_backend_templates(templates, backend):
        return filter(lambda template: template.backend == backend, templates)

    def add_templates(device, templates, ignore_backend_filter=False):
        if not ignore_backend_filter:
            templates = filter_backend_templates(templates, device.config.backend)
        device.config.templates.add(*templates)

    def remove_templates(device, templates, ignore_backend_filter=False):
        if not ignore_backend_filter:
            templates = filter_backend_templates(templates, device.config.backend)
        device.config.templates.remove(*templates)

    Device = load_model('config', 'Device')
    DeviceGroup = load_model('config', 'DeviceGroup')
    Template = load_model('config', 'Template')
    Config = load_model('config', 'Config')

    if model_name == Device._meta.model_name:
        device = Device.objects.get(pk=instance_id)
        if not hasattr(device, 'config'):
            return
        old_group_id = kwargs.get('old_group_id')
        group_id = kwargs.get('group_id')
        group = DeviceGroup.objects.get(pk=group_id)
        group_templates = group.templates.all()
        if old_group_id:
            old_group = DeviceGroup.objects.get(pk=old_group_id)
            old_group_templates = old_group.templates.all()
            remove_templates(device, old_group_templates)
        add_templates(device, group_templates)

    elif model_name == DeviceGroup._meta.model_name:
        device_group = DeviceGroup.objects.get(id=instance_id)
        templates = Template.objects.filter(pk__in=kwargs.get('templates'))
        old_templates = Template.objects.filter(pk__in=kwargs.get('old_templates'))
        for device in device_group.device_set.all():
            if not hasattr(device, 'config'):
                continue
            remove_templates(device, old_templates)
            add_templates(device, templates)

    elif model_name == Config._meta.model_name:
        config = Config.objects.get(pk=instance_id)
        device_group = config.device.group
        if not device_group:
            return
        templates = device_group.templates.filter(backend=kwargs.get('backend'))
        old_templates = device_group.templates.filter(backend=kwargs.get('old_backend'))
        ignore_backend_filter = True
        remove_templates(config.device, old_templates, ignore_backend_filter)
        add_templates(config.device, templates, ignore_backend_filter)
