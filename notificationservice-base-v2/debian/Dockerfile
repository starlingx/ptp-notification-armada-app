ARG BASE
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
ENV KUBE_LATEST_VERSION="v1.23.1"

RUN apt-get -y update \
 && apt-get -y install \
    gcc \
    python3-dev \
    python3 \
 && apt-get -y clean \
 && rm -rf /var/lib/apt/lists/*
RUN pip3 install --user pecan \
 && pip3 install oslo-config \
 && pip3 install oslo-messaging \
 && pip3 install WSME

WORKDIR /opt/
COPY ./ptptrackingfunction /opt/ptptrackingfunction
RUN cd /opt/ptptrackingfunction && python3 setup.py develop

CMD ["bash"]
