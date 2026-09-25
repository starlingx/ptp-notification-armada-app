ARG BASE
FROM ${BASE}

ARG WHEELS

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# install debian packages
# libcap2-bin provides setcap, used below to grant the Python interpreter the
# NET_ADMIN file capability so the non-root process can perform the DPLL/SyncE
# netlink reads (Kubernetes capabilities.add keeps NET_ADMIN in the bounding
# set for a non-root uid, and the file capability promotes it to effective).
RUN apt-get -y update \
&& apt-get -y install linuxptp wget libcap2-bin \
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

# Create a fixed, non-root system user/group for the tracking process. The uid
# and gid are pinned so the chart's runAsUser/runAsGroup match, so the container
# runtime (containerd device_ownership_from_security_context=true) chowns the
# injected /dev/ptp* nodes to this uid/gid — giving non-root device access with
# no capability at all. The app tree is made owned/readable by the user.
RUN groupadd -g 1000 ptp \
&& useradd -u 1000 -g 1000 -M -s /usr/sbin/nologin -d /opt ptp \
&& chown -R ptp:ptp /opt/ptptrackingfunction

# Grant the Python interpreter the NET_ADMIN file capability. The tracking code
# performs DPLL/SyncE clock-state reads over netlink (pynetlink NetlinkDPLL),
# which require NET_ADMIN. Kubernetes securityContext.capabilities.add keeps
# NET_ADMIN in the process bounding set for a non-root uid, but not in the
# effective set; the +ep file capability on the interpreter promotes it to
# effective when python is exec'd, so no root, no ambient-capability wrapper,
# and no CAP_DAC_OVERRIDE are needed. setcap targets the resolved real binary
# (python3 is a symlink) so it survives minor-version differences.
RUN PYBIN="$(readlink -f "$(command -v python3)")" \
&& setcap cap_net_admin+ep "$PYBIN" \
&& getcap "$PYBIN"

# Runtime user is provided by the chart via runAsUser/runAsGroup (1000). The
# image does not pin USER so the same image also works if run as root (the
# privileged fallback path); the securityContext selects the effective uid.
CMD ["bash"]