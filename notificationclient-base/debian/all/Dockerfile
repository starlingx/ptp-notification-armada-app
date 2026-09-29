ARG BASE
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get -y update \
 && apt-get -y install \
    python3-dev \
    python3 \
    curl \
 && apt-get -y clean \
 && rm -rf /var/lib/apt/lists/*
# Install pecan system-wide, consistent with the other packages below. The
# original used "pip3 install --user pecan", which lands in /root/.local (mode
# 0700) and is not on sys.path for a non-root runtime uid -- the import would
# fail with ModuleNotFoundError. Dropping --user lets it install into the
# system site-packages (/usr/local/lib/pythonX.Y/dist-packages) like the other
# packages, thanks to PIP_BREAK_SYSTEM_PACKAGES=1 set above (the base marks
# system Python externally-managed).
RUN pip3 install pecan \
 && pip3 install oslo-config \
 && pip3 install oslo-messaging \
 && pip3 install WSME \
 && pip3 install sqlalchemy==1.4.12 \
 && pip3 install waitress

WORKDIR /opt/
COPY ./notificationclient-sidecar /opt/notificationclient
RUN cd /opt/notificationclient && python3 setup.py develop

# Create a fixed, non-root user/group for the notification client sidecar. The
# uid/gid are pinned so the chart's runAsUser/runAsGroup can match. The sidecar
# only serves HTTP on port 8080 (unprivileged), writes a SQLite DB under an
# emptyDir-backed /opt/datastore, and logs to stdout -- no writable host paths
# and no capabilities. Make the app tree readable by the user. USER is left
# unset so the image is not tied to a single uid.
RUN groupadd -g 1000 notificationclient \
 && useradd -u 1000 -g 1000 -M -s /usr/sbin/nologin -d /opt notificationclient \
 && chown -R notificationclient:notificationclient /opt/notificationclient

CMD ["bash"]
