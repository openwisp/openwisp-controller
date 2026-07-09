#!/bin/bash

create_superuser () {
    local username="$1"
    local email="$2"
    local password="$3"
    cat <<EOF | python manage.py shell
from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username="$username").exists():
    User.objects.create_superuser("$username", "$email", "$password")
else:
    print('User "{}" exists already, not created'.format("$username"))
EOF
}

python manage.py migrate --no-input
create_superuser admin admin@example.com admin
celery -A openwisp2 worker -l info & \
python manage.py runserver 0.0.0.0:8000
