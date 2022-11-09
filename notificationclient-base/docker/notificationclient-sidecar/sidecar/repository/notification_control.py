#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
from pecan import conf
from notificationclientsdk.services.daemon import DaemonControl
from notificationclientsdk.common.helpers.nodeinfo_helper import NodeInfoHelper


REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "admin")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "admin")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
REGISTRATION_HOST = os.environ.get(
    "REGISTRATION_HOST", "registration.notification.svc.cluster.local")
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", "controller-0")
THIS_POD_IP = os.environ.get("THIS_POD_IP", "127.0.0.1")

NOTIFICATION_BROKER_USER = os.environ.get("NOTIFICATIONSERVICE_USER", "admin")
NOTIFICATION_BROKER_PASS = os.environ.get("NOTIFICATIONSERVICE_PASS", "admin")
NOTIFICATION_BROKER_PORT = os.environ.get("NOTIFICATIONSERVICE_PORT", "5672")

REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@{2}:{3}'.format(
  REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)

sqlalchemy_conf = dict(conf.sqlalchemy)
if sqlalchemy_conf.get('engine', None):
    sqlalchemy_conf.pop('engine')
sqlalchemy_conf_json = json.dumps(sqlalchemy_conf)
daemon_context = {
    'SQLALCHEMY_CONF_JSON': sqlalchemy_conf_json,
    'THIS_NODE_NAME': THIS_NODE_NAME,
    'REGISTRATION_TRANSPORT_ENDPOINT': REGISTRATION_TRANSPORT_ENDPOINT,
    'NOTIFICATION_BROKER_USER': NOTIFICATION_BROKER_USER,
    'NOTIFICATION_BROKER_PASS': NOTIFICATION_BROKER_PASS,
    'NOTIFICATION_BROKER_PORT': NOTIFICATION_BROKER_PORT
}
NodeInfoHelper.set_residing_node(THIS_NODE_NAME)
notification_control = DaemonControl(daemon_context)
