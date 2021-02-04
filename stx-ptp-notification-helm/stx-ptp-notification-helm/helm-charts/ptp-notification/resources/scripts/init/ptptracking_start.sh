#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
#!/bin/bash

# apt-get update -y
# #sleep infinity

# apt-get install -y gcc
# apt-get install -y python-dev
# apt-get install -y python3-pip

# export https_proxy=http://128.224.230.5:9090

# pip3 install oslo-config
# pip3 install oslo-messaging

cat <<EOF>/root/ptptracking-daemon.py
#!/usr/bin/python3
# -*- coding: UTF-8 -*-
import logging
LOG = logging.getLogger(__name__)

from trackingfunctionsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

import os
import json
import time  # 引入time模块
import oslo_messaging
from oslo_config import cfg

from trackingfunctionsdk.services.daemon import DaemonControl

THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE",'notification')
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-1')
THIS_POD_IP = os.environ.get("THIS_POD_IP",'127.0.0.1')
REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "admin")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "admin")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST",'registration.notification.svc.cluster.local')

REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@{2}:{3}'.format(
  REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)

NOTIFICATION_BROKER_USER = os.environ.get("NOTIFICATIONSERVICE_USER", "admin")
NOTIFICATION_BROKER_PASS = os.environ.get("NOTIFICATIONSERVICE_PASS", "admin")
NOTIFICATION_BROKER_PORT = os.environ.get("NOTIFICATIONSERVICE_PORT", "5672")

NOTIFICATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@{2}:{3}'.format(
  NOTIFICATION_BROKER_USER, NOTIFICATION_BROKER_PASS, THIS_POD_IP, NOTIFICATION_BROKER_PORT)

PTP_DEVICE_SIMULATED = os.environ.get("PTP_DEVICE_SIMULATED", False)

PTP_HOLDOVER_SECONDS = os.environ.get("PTP_HOLDOVER_SECONDS", 30)
PTP_POLL_FREQ_SECONDS = os.environ.get("PTP_POLL_FREQ_SECONDS", 2)

context = {
    'THIS_NAMESPACE': THIS_NAMESPACE,
    'THIS_NODE_NAME': THIS_NODE_NAME,
    'THIS_POD_IP': THIS_POD_IP,
    'REGISTRATION_TRANSPORT_ENDPOINT': REGISTRATION_TRANSPORT_ENDPOINT,
    'NOTIFICATION_TRANSPORT_ENDPOINT': NOTIFICATION_TRANSPORT_ENDPOINT,
    # 'NOTIFICATION_BROKER_USER': NOTIFICATION_BROKER_USER,
    # 'NOTIFICATION_BROKER_PASS': NOTIFICATION_BROKER_PASS,
    # 'NOTIFICATION_BROKER_PORT': NOTIFICATION_BROKER_PORT
    'ptptracker_context': {
        'device_simulated': PTP_DEVICE_SIMULATED,
        'holdover_seconds': PTP_HOLDOVER_SECONDS,
        'poll_freq_seconds': PTP_POLL_FREQ_SECONDS
    }
}

sqlalchemy_conf = {
    'url'           : 'sqlite:///apiserver.db',
    'echo'          : False,
    'echo_pool'     : False,
    'pool_recycle'  : 3600,
    'encoding'      : 'utf-8'
}
sqlalchemy_conf_json = json.dumps(sqlalchemy_conf)
default_daemoncontrol = DaemonControl(sqlalchemy_conf_json, json.dumps(context))

default_daemoncontrol.refresh()
while True:
    pass

EOF



echo "done"

PYTHONPATH=/opt/ptptrackingfunction python3 /root/ptptracking-daemon.py &

sleep infinity
