#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
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

cat <<EOF>/root/notification_control.py
import os
import time
import json
from pecan import conf
from locationservicesdk.services.daemon import DaemonControl

REGISTRATION_USER = os.environ.get("REGISTRATION_USER", "admin")
REGISTRATION_PASS = os.environ.get("REGISTRATION_PASS", "admin")
REGISTRATION_PORT = os.environ.get("REGISTRATION_PORT", "5672")
REGISTRATION_HOST = os.environ.get("REGISTRATION_HOST",'registration.notification.svc.cluster.local')
THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')
THIS_POD_IP = os.environ.get("THIS_POD_IP",'127.0.0.1')

REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@[{2}]:{3}'.format(
  REGISTRATION_USER, REGISTRATION_PASS, REGISTRATION_HOST, REGISTRATION_PORT)

sqlalchemy_conf_json=json.dumps({})
LocationInfo = {
            'NodeName': THIS_NODE_NAME,
            'PodIP': THIS_POD_IP,
            'ResourceTypes': ['PTP'],
            'Timestamp': time.time()
            }
location_info_json = json.dumps(LocationInfo)
notification_control = DaemonControl(
  sqlalchemy_conf_json, REGISTRATION_TRANSPORT_ENDPOINT, location_info_json)


EOF

cp /root/notification_control.py /opt/locationservice/apiserver/repository

cd /opt/locationservice && pecan serve config.py &


sleep infinity
