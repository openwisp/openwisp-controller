from __future__ import absolute_import, unicode_literals

from django_netjsonconfig.celery import app as django_netjsonconfig_celery_app

from .celery import app as celery_app

__all__ = ['celery_app', 'django_netjsonconfig_celery_app']
