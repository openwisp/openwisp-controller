FROM python:3.7-alpine

WORKDIR /opt/openwisp/
CMD ["sh", "docker-entrypoint.sh"]
EXPOSE 8000
ENV NAME=openwisp-controller \
    PYTHONBUFFERED=1

RUN apk add --no-cache \
            --update zlib-dev jpeg-dev libffi-dev gettext gcc openssl tzdata && \
    apk add --no-cache \
            --repository http://dl-cdn.alpinelinux.org/alpine/edge/testing \
            --update geos-dev gdal-dev libspatialite && \
    apk add --no-cache \
            --update \
            --virtual .build-deps postgresql-dev git build-base linux-headers openssl-dev

# TODO: Update this and remove django-netjsonconfig
RUN pip install django-netjsonconfig openwisp-utils scp celery asgi_redis \
                django-loci paramiko openwisp-users cryptography==2.3.1 \
                djangorestframework-gis redis service_identity django-redis

ADD . /opt/openwisp

RUN pip install -U . && \
    pip install https://github.com/openwisp/openwisp-users/tarball/master && \
    pip install https://github.com/openwisp/django-netjsonconfig/tarball/master && \
    pip install https://github.com/openwisp/django-x509/tarball/master && \
    pip install https://github.com/openwisp/openwisp-utils/tarball/master

WORKDIR /opt/openwisp/tests/
