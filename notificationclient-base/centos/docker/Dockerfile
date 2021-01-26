ARG BASE
FROM ${BASE}

ARG STX_REPO_FILE=/etc/yum.repos.d/stx.repo

ENV KUBE_LATEST_VERSION="v1.18.3"

RUN set -ex ;\
    yum install --disablerepo=* \
        $(grep '^name=' ${STX_REPO_FILE} | awk -F '=' '{printf "--enablerepo=" $2 " "}') \
        -y \
        gcc python3-devel python3-pip \
        && pip3 install --user pecan \
        && pip3 install oslo-config \
        && pip3 install oslo-messaging \
        && pip3 install WSME \
        && pip3 install sqlalchemy

WORKDIR /opt/
COPY ./notificationclient-sidecar /opt/notificationclient
RUN cd /opt/notificationclient && python3 setup.py develop

CMD ["bash"]
