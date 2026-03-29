from celery import Task

from . import settings as app_settings


class OpenwispCeleryTask(Task):
    soft_time_limit = app_settings.CELERY_SOFT_TIME_LIMIT
    time_limit = app_settings.CELERY_HARD_TIME_LIMIT
