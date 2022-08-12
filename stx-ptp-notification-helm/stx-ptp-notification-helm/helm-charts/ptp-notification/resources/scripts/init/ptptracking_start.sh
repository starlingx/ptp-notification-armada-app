#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
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

from trackingfunctionsdk.services.daemon import DaemonControl

THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE", 'notification')
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", 'controller-0')
THIS_POD_IP = os.environ.get("THIS_POD_IP", '127.0.0.1')
REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "guest")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "guest")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
# REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST", 'registration.notification.svc.cluster.local')
REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST", 'localhost')

# 'rabbit://admin:admin@[127.0.0.1]:5672/'
# 'rabbit://admin:admin@[::1]:5672/'
REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@[{2}]:{3}'.format(
    REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)

NOTIFICATION_BROKER_USER = os.environ.get("NOTIFICATIONSERVICE_USER", "guest")
NOTIFICATION_BROKER_PASS = os.environ.get("NOTIFICATIONSERVICE_PASS", "guest")
NOTIFICATION_BROKER_PORT = os.environ.get("NOTIFICATIONSERVICE_PORT", "5672")

NOTIFICATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@[{2}]:{3}'.format(
    NOTIFICATION_BROKER_USER, NOTIFICATION_BROKER_PASS, THIS_POD_IP, NOTIFICATION_BROKER_PORT)

PTP_DEVICE_SIMULATED = os.environ.get("PTP_DEVICE_SIMULATED", True)

PTP_HOLDOVER_SECONDS = os.environ.get("PTP_HOLDOVER_SECONDS", 30)
PTP_POLL_FREQ_SECONDS = os.environ.get("PTP_POLL_FREQ_SECONDS", 2)

GNSS_HOLDOVER_SECONDS = os.environ.get("GNSS_HOLDOVER_SECONDS", 30)
GNSS_POLL_FREQ_SECONDS = os.environ.get("GNSS_POLL_FREQ_SECONDS", 2)

OS_CLOCK_HOLDOVER_SECONDS = os.environ.get("OS_CLOCK_HOLDOVER_SECONDS", 30)
OS_CLOCK_POLL_FREQ_SECONDS = os.environ.get("OS_CLOCK_POLL_FREQ_SECONDS", 2)

OVERALL_HOLDOVER_SECONDS = os.environ.get("OVERALL_HOLDOVER_SECONDS", 30)
OVERALL_POLL_FREQ_SECONDS = os.environ.get("OVERALL_POLL_FREQ_SECONDS", 2)

GNSS_CONFIGS = json.loads(os.environ.get("TS2PHC_CONFIGS", ["/ptp/ptpinstance/ts2phc-ts1.conf"]))
PHC2SYS_CONFIG = os.environ.get("PHC2SYS_CONFIG", "/ptp/ptpinstance/phc2sys-phc-inst1.conf")

context = {
    'THIS_NAMESPACE': THIS_NAMESPACE,
    'THIS_NODE_NAME': THIS_NODE_NAME,
    'THIS_POD_IP': THIS_POD_IP,
    'REGISTRATION_TRANSPORT_ENDPOINT': REGISTRATION_TRANSPORT_ENDPOINT,
    'NOTIFICATION_TRANSPORT_ENDPOINT': NOTIFICATION_TRANSPORT_ENDPOINT,
    'GNSS_CONFIGS': GNSS_CONFIGS,
    'PHC2SYS_CONFIG': PHC2SYS_CONFIG,

    'ptptracker_context': {
        'device_simulated': PTP_DEVICE_SIMULATED,
        'holdover_seconds': PTP_HOLDOVER_SECONDS,
        'poll_freq_seconds': PTP_POLL_FREQ_SECONDS
    },
    'gnsstracker_context': {
        'holdover_seconds': GNSS_HOLDOVER_SECONDS,
        'poll_freq_seconds': GNSS_POLL_FREQ_SECONDS
    },
    'osclocktracker_context': {
        'holdover_seconds': OS_CLOCK_HOLDOVER_SECONDS,
        'poll_freq_seconds': OS_CLOCK_POLL_FREQ_SECONDS
    },
    'overalltracker_context': {
        'holdover_seconds': OVERALL_HOLDOVER_SECONDS,
        'poll_freq_seconds': OVERALL_POLL_FREQ_SECONDS
    }
}

sqlalchemy_conf = {
    'url': 'sqlite:///apiserver.db',
    'echo': False,
    'echo_pool': False,
    'pool_recycle': 3600,
    'encoding': 'utf-8'
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
