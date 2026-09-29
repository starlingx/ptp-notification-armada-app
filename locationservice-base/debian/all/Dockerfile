ARG BASE
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get -y update \
 && apt-get -y install \
    python3-dev \
    python3 \
 && apt-get -y clean \
 && rm -rf /var/lib/apt/lists/*
# Install pecan system-wide, consistent with the other packages below. The
# original used "pip3 install --user pecan", which lands in /root/.local (mode
# 0700) and is not on sys.path for a non-root runtime uid -- the import would
# fail with ModuleNotFoundError. Dropping --user lets the install go to the
# system site-packages (/usr/local/lib/pythonX.Y/dist-packages) like
# oslo-config/oslo-messaging/WSME, thanks to PIP_BREAK_SYSTEM_PACKAGES=1 set
# above (the base marks system Python externally-managed). No --user was ever
# needed; it was the sole reason pecan landed in an unreadable per-root dir.
RUN pip3 install pecan \
 && pip3 install oslo-config \
 && pip3 install oslo-messaging \
 && pip3 install WSME

WORKDIR /opt/
COPY ./locationservice /opt/locationservice
RUN cd /opt/locationservice && python3 setup.py develop

# Create a fixed, non-root user/group for the location service. The uid/gid
# are pinned so the chart's runAsUser/runAsGroup can match. The service only
# serves HTTP on port 8080 (unprivileged) and logs to stdout -- it needs no
# writable host paths and no capabilities. Make the app tree readable by the
# user.
RUN groupadd -g 1000 location \
 && useradd -u 1000 -g 1000 -M -s /usr/sbin/nologin -d /opt location \
 && chown -R location:location /opt/locationservice

# Runtime user is provided by the chart via runAsUser/runAsGroup (1000). USER
# is left unset so the image is not tied to a single uid.
CMD ["bash"]
