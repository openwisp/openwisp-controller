FROM python:3.9-slim-bullseye

# This Dockerfile adds a non-root user with sudo access. Use the "remoteUser"
# property in devcontainer.json to use it. On Linux, the container user's GID/UIDs
# will be updated to match your local UID/GID (when using the dockerFile property).
# See https://aka.ms/vscode-remote/containers/non-root-user for details.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Ensure git credentials are copied to vscode user we will be using instead of root
ENV HOME /home/vscode

RUN apt update \
    #
    # Create a non-root user to use if preferred - see https://aka.ms/vscode-remote/containers/non-root-user.
    && groupadd --gid $USER_GID $USERNAME \
    && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
    #
    # [Optional] Add sudo support
    && apt install --yes sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    #
    # Install tools and dependencies
    && apt install --yes zlib1g-dev libjpeg-dev gdal-bin libproj-dev \
    libgeos-dev libspatialite-dev libsqlite3-mod-spatialite \
    sqlite3 libsqlite3-dev openssl libssl-dev \
    celery redis nodejs npm \
    # Install my favs
    vim git \
    # Install npm deps
    && npm install -g jshint stylelint \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip/* /tmp/*
# Setup OpenWISP
COPY requirements-test.txt requirements.txt /opt/openwisp/
RUN pip install -r /opt/openwisp/requirements.txt \
    && pip install -r /opt/openwisp/requirements-test.txt \
    && pip install redis \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip/* /tmp/*

# Clean up
RUN sudo apt --yes autoremove

ADD . /opt/openwisp
RUN pip install -U /opt/openwisp \
    && rm -rf /var/lib/apt/lists/* /root/.cache/pip/* /tmp/*

WORKDIR /opt/openwisp/tests/
ENV NAME=openwisp-controller \
    PYTHONBUFFERED=1
