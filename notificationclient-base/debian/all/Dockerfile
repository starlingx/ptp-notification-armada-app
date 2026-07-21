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
 && pip3 install waitress

WORKDIR /opt/
COPY ./notificationclient-sidecar /opt/notificationclient
RUN cd /opt/notificationclient && python3 setup.py develop

CMD ["bash"]
