#
# Copyright (c) 2021-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
#!/usr/bin/python3
# -*- coding: UTF-8 -*-
import glob
import json
import logging
import os
import re

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.services.daemon import DaemonControl

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE", 'notification')
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", 'controller-0')
THIS_POD_IP = os.environ.get("THIS_POD_IP", '127.0.0.1')
REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "guest")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "guest")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
# REGISTRATION_HOST = \
#   os.environ.get("REGISTRATION_HOST",
#                  'registration.notification.svc.cluster.local')
REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST", 'localhost')

# 'rabbit://admin:admin@[127.0.0.1]:5672/'
# 'rabbit://admin:admin@[::1]:5672/'
REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@[{2}]:{3}'.format(
    REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)

NOTIFICATION_BROKER_USER = os.environ.get("NOTIFICATIONSERVICE_USER", "guest")
NOTIFICATION_BROKER_PASS = os.environ.get("NOTIFICATIONSERVICE_PASS", "guest")
NOTIFICATION_BROKER_PORT = os.environ.get("NOTIFICATIONSERVICE_PORT", "5672")

NOTIFICATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@[{2}]:{3}'.format(
    NOTIFICATION_BROKER_USER, NOTIFICATION_BROKER_PASS, THIS_POD_IP,
    NOTIFICATION_BROKER_PORT)

PTP_DEVICE_SIMULATED = os.environ.get("PTP_DEVICE_SIMULATED", True)

PTP_HOLDOVER_SECONDS = os.environ.get("PTP_HOLDOVER_SECONDS", 30)
GNSS_HOLDOVER_SECONDS = os.environ.get("GNSS_HOLDOVER_SECONDS", 30)
OS_CLOCK_HOLDOVER_SECONDS = os.environ.get("OS_CLOCK_HOLDOVER_SECONDS", 30)
OVERALL_HOLDOVER_SECONDS = os.environ.get("OVERALL_HOLDOVER_SECONDS", 30)

PHC2SYS_CONFIG = None
PHC2SYS_SERVICE_NAME = None
if os.environ.get("PHC2SYS_SERVICE_NAME").lower() == "false":
    LOG.info("OS Clock tracking disabled.")
else:
    PHC2SYS_CONFIGS = glob.glob(constants.PHC2SYS_CONFIG_PATH + "phc2sys-*")
    LOG.debug('Looked for phc2sys configuration file(s) in %s, found %d'
              % (constants.PHC2SYS_CONFIG_PATH, len(PHC2SYS_CONFIGS)))
    if len(PHC2SYS_CONFIGS) == 0:
        LOG.warning("No phc2sys config found.")
    else:
        PHC2SYS_CONFIG = PHC2SYS_CONFIGS[0]
        if len(PHC2SYS_CONFIGS) > 1:
            LOG.warning("Multiple phc2sys instances found, selecting %s" %
                        PHC2SYS_CONFIG)
        pattern = '(?<=' + constants.PHC2SYS_CONFIG_PATH + \
                  'phc2sys-).*(?=.conf)'
        match = re.search(pattern, PHC2SYS_CONFIG)
        PHC2SYS_SERVICE_NAME = match.group()

PTP4L_CONFIGS = []
PTP4L_INSTANCES = []
if os.environ.get("PTP4L_SERVICE_NAME").lower() == "false":
    LOG.info("PTP4L instance tracking disabled.")
else:
    PTP4L_CONFIGS = glob.glob(constants.PTP_CONFIG_PATH + "ptp4l-*")
    LOG.debug('Looked for ptp4l configuration file(s) in %s, found %d'
              % (constants.PTP_CONFIG_PATH, len(PTP4L_CONFIGS)))
    PTP4L_INSTANCES = []
    pattern = '(?<=' + constants.PTP_CONFIG_PATH + 'ptp4l-).*(?=.conf)'
    for conf in PTP4L_CONFIGS:
        match = re.search(pattern, conf)
        PTP4L_INSTANCES.append(match.group())

GNSS_CONFIGS = []
GNSS_INSTANCES = []
if os.environ.get("TS2PHC_SERVICE_NAME").lower() == "false":
    LOG.info("GNSS instance tracking disabled.")
else:
    GNSS_CONFIGS = glob.glob(constants.TS2PHC_CONFIG_PATH + "ts2phc-*")
    LOG.debug('Looked for ts2phc configuration file(s) in %s, found %d'
              % (constants.TS2PHC_CONFIG_PATH, len(GNSS_CONFIGS)))
    GNSS_INSTANCES = []
    pattern = '(?<=' + constants.TS2PHC_CONFIG_PATH + 'ts2phc-).*(?=.conf)'
    for conf in GNSS_CONFIGS:
        match = re.search(pattern, conf)
        GNSS_INSTANCES.append(match.group())

context = {
    'THIS_NAMESPACE': THIS_NAMESPACE,
    'THIS_NODE_NAME': THIS_NODE_NAME,
    'THIS_POD_IP': THIS_POD_IP,
    'REGISTRATION_TRANSPORT_ENDPOINT': REGISTRATION_TRANSPORT_ENDPOINT,
    'NOTIFICATION_TRANSPORT_ENDPOINT': NOTIFICATION_TRANSPORT_ENDPOINT,
    'GNSS_CONFIGS': GNSS_CONFIGS,
    'PHC2SYS_CONFIG': PHC2SYS_CONFIG,
    'PHC2SYS_SERVICE_NAME': PHC2SYS_SERVICE_NAME,
    'PTP4L_CONFIGS': PTP4L_CONFIGS,
    'GNSS_INSTANCES': GNSS_INSTANCES,
    'PTP4L_INSTANCES': PTP4L_INSTANCES,

    'ptptracker_context': {
        'device_simulated': PTP_DEVICE_SIMULATED,
        'holdover_seconds': PTP_HOLDOVER_SECONDS
    },
    'gnsstracker_context': {
        'holdover_seconds': GNSS_HOLDOVER_SECONDS
    },
    'osclocktracker_context': {
        'holdover_seconds': OS_CLOCK_HOLDOVER_SECONDS
    },
    'overalltracker_context': {
        'holdover_seconds': OVERALL_HOLDOVER_SECONDS
    }
}

sqlalchemy_conf = {
    'url': 'sqlite:///apiserver.db',
    'echo': False,
    'echo_pool': False,
    'pool_recycle': 3600,
    'encoding': 'utf-8'
}
LOG.info("PTP tracking service startup context %s" % context)
sqlalchemy_conf_json = json.dumps(sqlalchemy_conf)
default_daemoncontrol = DaemonControl(sqlalchemy_conf_json,
                                      json.dumps(context))

default_daemoncontrol.refresh()
