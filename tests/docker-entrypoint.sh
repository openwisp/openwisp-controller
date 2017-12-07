#!/bin/bash

echo "EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'" > local_settings.py
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py runserver 0.0.0.0:8000
