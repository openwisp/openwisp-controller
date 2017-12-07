FROM python:3-onbuild

WORKDIR .
RUN apt-get update && apt-get install -y \
    openssl \
    sqlite3 \
    libsqlite3-dev \
    libssl-dev \
    gdal-bin \
    libproj-dev \
    libgeos-dev \
    libspatialite-dev
RUN pip3 install -U pip setuptools wheel
RUN pip3 install -U .
RUN echo "openwisp-controller installed"
WORKDIR tests/
CMD ["./docker-entrypoint.sh"]
EXPOSE 8000

ENV NAME openwisp-controller
