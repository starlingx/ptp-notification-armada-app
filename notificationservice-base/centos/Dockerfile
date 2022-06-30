ARG BASE
FROM ${BASE}

ARG STX_REPO_FILE=/etc/yum.repos.d/stx.repo

ENV KUBE_LATEST_VERSION="v1.23.1"

RUN set -ex ;\
    yum install --disablerepo=* \
        $(grep '^name=' ${STX_REPO_FILE} | awk -F '=' '{printf "--enablerepo=" $2 " "}') \
        -y \
        gcc python3-devel python3-pip \
        && pip3 install --user pecan \
        && pip3 install pygtail \
        && pip3 install oslo-config \
        && pip3 install oslo-messaging \
        && pip3 install WSME

WORKDIR /opt/
COPY ./ptptrackingfunction /opt/ptptrackingfunction
RUN cd /opt/ptptrackingfunction && python3 setup.py develop

CMD ["bash"]
