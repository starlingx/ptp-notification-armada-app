ARG BASE
FROM ${BASE}

ARG WHEELS

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# install debian packages
RUN apt-get -y update \
&& apt-get -y install linuxptp wget \
&& apt-get -y clean \
&& rm -rf /var/lib/apt/lists/*

# install pip packages
RUN mkdir -p /tmp/wheels
RUN wget -P /tmp/wheels ${WHEELS}
WORKDIR /tmp/wheels
RUN tar xvf /tmp/wheels/*.tar

RUN pip3 install --find-links=/tmp/wheels\
    jsonschema \
    oslo.config \
    oslo.messaging \
    pecan \
    pyyaml \
    setuptools \
    watchdog \
    wsme
RUN pip3 install --no-index --find-links=/tmp/wheels pynetlink

# clean up step
RUN rm -rf /tmp/wheels

WORKDIR /opt/
COPY ./ptptrackingfunction /opt/ptptrackingfunction
RUN cd /opt/ptptrackingfunction && python3 setup.py develop

CMD ["bash"]