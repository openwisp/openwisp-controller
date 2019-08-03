from __future__ import absolute_import, unicode_literals

from celery import shared_task
from openwisp_controller.config.models import TemplateSubscription


@shared_task()
def synchronize_templates():
    TemplateSubscription.synchronize_templates()
