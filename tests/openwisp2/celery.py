import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openwisp2.settings")

app = Celery("openwisp2")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
