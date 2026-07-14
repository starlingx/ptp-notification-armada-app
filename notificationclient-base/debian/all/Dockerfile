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
RUN pip3 install --user pecan \
 && pip3 install oslo-config \
 && pip3 install oslo-messaging \
 && pip3 install WSME \
 && pip3 install sqlalchemy==1.4.12 \
 && pip3 install waitress \
 && pip3 install --upgrade \
    "mako>=1.3.12" \
    "msgpack>=1.2.1" \
    "urllib3>=2.7.0" \
    "requests>=2.33.0" \
    "webob>=1.8.10" \
    "idna>=3.15"

WORKDIR /opt/
COPY ./notificationclient-sidecar /opt/notificationclient
RUN cd /opt/notificationclient && python3 setup.py develop

CMD ["bash"]
