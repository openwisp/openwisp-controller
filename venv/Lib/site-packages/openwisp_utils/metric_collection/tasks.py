from celery import shared_task

from ..tasks import OpenwispCeleryTask
from .models import OpenwispVersion


@shared_task(base=OpenwispCeleryTask)
def send_usage_metrics(category="Heartbeat"):
    OpenwispVersion.send_usage_metrics(category)
