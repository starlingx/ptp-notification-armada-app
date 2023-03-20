#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json

import oslo_messaging
from oslo_config import cfg


def setup_client(rpc_endpoint_info, topic, server):
    oslo_messaging.set_transport_defaults(rpc_endpoint_info.Exchange)
    transport = oslo_messaging.get_rpc_transport(cfg.CONF, url=rpc_endpoint_info.TransportEndpoint)
    target = oslo_messaging.Target(topic=topic,
                                   version=rpc_endpoint_info.Version,
                                   server=server,
                                   namespace=rpc_endpoint_info.Namespace)
    client = oslo_messaging.get_rpc_client(transport, target)
    return client

def get_transport(rpc_endpoint_info):
    oslo_messaging.set_transport_defaults(rpc_endpoint_info.Exchange)
    return oslo_messaging.get_rpc_transport(cfg.CONF, url=rpc_endpoint_info.TransportEndpoint)
