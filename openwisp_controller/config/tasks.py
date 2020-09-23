import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.exceptions import ObjectDoesNotExist
from swapper import load_model

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=1200)
def update_template_related_config_status(template_pk):
    """
    Flags config objects related to
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
