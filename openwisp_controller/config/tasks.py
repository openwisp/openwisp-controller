import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

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


@shared_task
def invalidate_devicegroup_cache(instance_id, model_name):
    from .api.views import DeviceGroupFromCommonName

    DeviceGroup = load_model('config', 'DeviceGroup')
    Organization = load_model('openwisp_users', 'Organization')
    Cert = load_model('django_x509', 'Cert')
    if model_name == DeviceGroup._meta.model_name:
        DeviceGroupFromCommonName.devicegroup_change_invalidates_cache(instance_id)
    elif model_name == Organization._meta.model_name:
        DeviceGroupFromCommonName.organization_change_invalidates_cache(instance_id)
    elif model_name == Cert._meta.model_name:
        DeviceGroupFromCommonName.certificate_change_invalidates_cache(instance_id)
