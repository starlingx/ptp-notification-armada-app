#
# Copyright (c) 2023-2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#


# !/usr/bin/python3
# -*- coding: UTF-8 -*-
import logging

LOG = logging.getLogger(__name__)
from trackingfunctionsdk.common.helpers import log_helper

log_helper.config_logger(LOG)
import os
import json
import time
import glob
import re
import ipaddress
import oslo_messaging
from oslo_config import cfg
from trackingfunctionsdk.services.daemon import DaemonControl

def build_rabbitmq_endpoint(user, password, host, port):
    """Build RabitMQ endpoint URL"""

    """Only IPv6 addresses are enclosed in square brackets."""
    # 'rabbit://admin:admin@127.0.0.1:5672/'
    # 'rabbit://admin:admin@registration.notification.svc.cluster.local:5672/'
    # 'rabbit://admin:admin@[::1]:5672/'
    endpoint_format = 'rabbit://{0}:{1}@{2}:{3}'
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 6:
            endpoint_format = 'rabbit://{0}:{1}@[{2}]:{3}'
    except ValueError:
        pass

    return endpoint_format.format(user, password, host, port)

THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE", 'notification')
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", 'controller-1')
THIS_POD_IP = os.environ.get("THIS_POD_IP", '127.0.0.1')
REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "admin")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "admin")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST",
                                   'registration.notification.svc.cluster.local')
REGISTRATION_TRANSPORT_ENDPOINT = build_rabbitmq_endpoint(
    REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)
NOTIFICATION_BROKER_USER = os.environ.get("NOTIFICATIONSERVICE_USER", "admin")
NOTIFICATION_BROKER_PASS = os.environ.get("NOTIFICATIONSERVICE_PASS", "admin")
NOTIFICATION_BROKER_PORT = os.environ.get("NOTIFICATIONSERVICE_PORT", "5672")
NOTIFICATION_TRANSPORT_ENDPOINT = build_rabbitmq_endpoint(
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
    'url': 'sqlite:///apiserver.db',
    'echo': False,
    'echo_pool': False,
    'pool_recycle': 3600,
    'encoding': 'utf-8'
}
sqlalchemy_conf_json = json.dumps(sqlalchemy_conf)
default_daemoncontrol = DaemonControl(sqlalchemy_conf_json, json.dumps(context))

if os.path.exists('/ptp/linuxptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/linuxptp/ptpinstance/'
elif os.path.exists('/ptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/ptpinstance/'
else:
    LINUXPTP_CONFIG_PATH = '/ptp/'

ptp4l_service_name = os.environ.get('PTP4L_SERVICE_NAME', 'ptp4l')
phc2sys_service_name = os.environ.get('PHC2SYS_SERVICE_NAME', 'phc2sys')

pmc = False
ptp4l = False
phc2sys = False
ptp4lconf = False
phc2sysconf = False

if os.path.isfile('/usr/sbin/pmc'):
    pmc = True

# Check ptp4l config, auto-detect if not found
if os.path.isfile('%sptp4l-%s.conf' % (LINUXPTP_CONFIG_PATH, ptp4l_service_name)):
    ptp4lconf = True
else:
    try:
        LOG.warning("Unable to locate ptp4l config file, attempting to auto-detect")
        ptp4l_detect_config = glob.glob(LINUXPTP_CONFIG_PATH + "ptp4l*.conf")[0]
        pattern = '(?<=' + LINUXPTP_CONFIG_PATH + 'ptp4l-).*(?=.conf)'
        match = re.search(pattern, ptp4l_detect_config)
        ptp4l_service_name = match.group()
        LOG.info("Using ptp4l conf: %s and ptp4l service name %s"
                % (ptp4l_detect_config, ptp4l_service_name))
        LOG.info("Set Helm overrides to override auto-detection")
        ptp4lconf = True
    except:
        LOG.warning("Unable to locate ptp4l config, auto-detect failed.")

# Check phc2sys config, auto-detect if not found
if os.path.isfile('%sphc2sys-%s.conf' % (LINUXPTP_CONFIG_PATH, phc2sys_service_name)):
    phc2sysconf = True
else:
    try:
        LOG.warning("Unable to locate phc2sys config file, attempting to auto-detect")
        phc2sys_detect_config = glob.glob(LINUXPTP_CONFIG_PATH + "phc2sys*.conf")[0]
        pattern = '(?<=' + LINUXPTP_CONFIG_PATH + 'phc2sys-).*(?=.conf)'
        match = re.search(pattern, phc2sys_detect_config)
        phc2sys_service_name = match.group()
        LOG.info("Using phc2sys conf: %s and phc2sys service name: %s"
                % (phc2sys_detect_config, phc2sys_service_name))
        LOG.info("Set Helm overrides to override auto-detection")
        phc2sysconf = True
    except:
        LOG.warning("Unable to locate phc2sys config, auto-detect failed.")

# Check that ptp4l and phc2sys are running
if os.path.isfile('/var/run/ptp4l-%s.pid' % ptp4l_service_name):
    ptp4l = True
else:
    LOG.warning("Unable to locate .pid file for %s" % ptp4l_service_name)
if os.path.isfile('/var/run/phc2sys-%s.pid' % phc2sys_service_name):
    phc2sys = True
else:
    LOG.warning("Unable to locate .pid file for %s" % phc2sys_service_name)


if pmc and ptp4l and phc2sys and ptp4lconf and phc2sysconf:
    LOG.info("Located ptp4l and phc2sys configs, starting ptp-notification")
    default_daemoncontrol.refresh()
else:
    LOG.warning("Please configure application overrides and ensure that ptp services are running.")
    while True:
        pass
