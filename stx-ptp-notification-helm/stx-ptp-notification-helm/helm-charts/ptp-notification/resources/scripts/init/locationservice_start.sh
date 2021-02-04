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

cat <<EOF>/root/location-query-server.py
#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import os
import json
import time  # 引入time模块
import oslo_messaging
from oslo_config import cfg


THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-1')
THIS_POD_IP = os.environ.get("THIS_POD_IP",'127.0.0.1')
THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE",'notification')

rabbituser = os.environ.get("REGISTRATION_USER",'admin')
rabbitpasswd = os.environ.get("REGISTRATION_PASS",'admin')
rabbitip = "registration.{0}.svc.cluster.local".format(THIS_NAMESPACE)
rabbitport = os.environ.get("REGISTRATION_PORT",'5672')
# 'rabbit://admin:admin@172.16.192.78:5672/'
rabbitendpoint = "rabbit://{0}:{1}@{2}:{3}".format(
    rabbituser, rabbitpasswd, rabbitip, rabbitport)

class LocationInfoEndpoint(object):
    target = oslo_messaging.Target(namespace='notification', version='1.0')

    def __init__(self, server):
        self.server = server

    def QueryLocation(self, ctx, rpc_kwargs):
        print ("QueryLocation called %s" %rpc_kwargs)
        LocationInfo = {
            'NodeName': THIS_NODE_NAME,
            'PodIP': THIS_POD_IP,
            'ResourceTypes': ['PTP'],
            'Timestamp': time.time()
        }

        return LocationInfo

oslo_messaging.set_transport_defaults('notification_exchange')
transport = oslo_messaging.get_rpc_transport(cfg.CONF, url=rabbitendpoint)
target = oslo_messaging.Target(topic='LocationQuery', server="LocationService-{0}".format(THIS_NODE_NAME))
endpoints = [LocationInfoEndpoint(None)]
server = oslo_messaging.get_rpc_server(transport, target, endpoints,
                                      executor=None)
# oslo_messaging.server.ExecutorLoadFailure:
# Failed to load executor "blocking": Executor should be None or 'eventlet' and 'threading'
server.start()
print("LocationService-{0} starts".format(THIS_NODE_NAME))
server.wait()

EOF



cat <<EOF>/root/location-announce.py
#!/usr/bin/python3
# -*- coding: UTF-8 -*-

import os
import json
import time  # 引入time模块
import oslo_messaging
from oslo_config import cfg
from webob.exc import HTTPException, HTTPNotFound, HTTPBadRequest, HTTPClientError, HTTPServerError


THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-1')
THIS_POD_IP = os.environ.get("THIS_POD_IP",'127.0.0.1')
THIS_NAMESPACE = os.environ.get("THIS_NAMESPACE",'notification')

rabbituser = os.environ.get("REGISTRATION_USER",'admin')
rabbitpasswd = os.environ.get("REGISTRATION_PASS",'admin')
rabbitip = "registration.{0}.svc.cluster.local".format(THIS_NAMESPACE)
rabbitport = os.environ.get("REGISTRATION_PORT",'5672')
rabbitendpoint = "rabbit://{0}:{1}@{2}:{3}".format(
    rabbituser, rabbitpasswd, rabbitip, rabbitport)

oslo_messaging.set_transport_defaults('notification_exchange')
transport = oslo_messaging.get_rpc_transport(cfg.CONF, url=rabbitendpoint)

location_topic='LocationListener-{0}'.format(THIS_NODE_NAME),
target = oslo_messaging.Target(
    topic=location_topic,
    fanout=True,
    version='1.0', namespace='notification')

client = oslo_messaging.RPCClient(transport, target)
LocationInfo = {
            'NodeName': THIS_NODE_NAME,
            'PodIP': THIS_POD_IP,
            'ResourceTypes': ['PTP'],
            'Timestamp': time.time()
            }

while True:
    try:
        client.cast({}, 'NotifyLocation', location_info=LocationInfo)
        print("Announce location info:{0}@Topic:{1}".format(LocationInfo, location_topic))
    except HTTPNotFound as ex:
        print("Failed to publish location due to not found: {0}".format(str(ex)))
        continue
    except Exception as ex:
        print("Failed to publish location due to: {0}".format(str(ex)))
        continue
    else:
        break

EOF

echo "done"

# python3 /root/location-query-server.py &

# python3 /root/location-announce.py

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

REGISTRATION_TRANSPORT_ENDPOINT = 'rabbit://{0}:{1}@{2}:{3}'.format(
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
