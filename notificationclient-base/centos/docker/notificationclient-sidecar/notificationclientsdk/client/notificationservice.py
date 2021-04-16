#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
import time
import oslo_messaging
from oslo_config import cfg

from notificationclientsdk.model.dto.rpc_endpoint import RpcEndpointInfo

from notificationclientsdk.client.base import BrokerClientBase

from notificationclientsdk.model.dto.subscription import SubscriptionInfo
from notificationclientsdk.repository.subscription_repo import SubscriptionRepo

import logging

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class NotificationHandlerBase(object):

    def __init__(self):
        pass

    def handle(self, notification_info):
        return False

class NotificationServiceClient(BrokerClientBase):
    class ListenerEndpoint(object):
        target = oslo_messaging.Target(namespace='notification', version='1.0')

        def __init__(self, handler):
            self.handler = handler

        def NotifyStatus(self, ctx, notification):
            LOG.debug("NotificationServiceClient NotifyStatus called %s" % notification)
            self.handler.handle(notification)
            return time.time()

    '''Init client to notification service'''
    def __init__(self, target_node_name, notificationservice_transport_endpoint, broker_pod_ip):
        self.Id = id(self)
        self.target_node_name = target_node_name
        self.broker_pod_ip = broker_pod_ip
        super(NotificationServiceClient, self).__init__(
            '{0}'.format(target_node_name),
            notificationservice_transport_endpoint)
        return

    def __del__(self):
        super(NotificationServiceClient, self).__del__()
        return

    def query_resource_status(self, resource_type,
        timeout=None, retry=None, resource_qualifier_json=None):
        topic = '{0}-Status'.format(resource_type)
        server = '{0}-Tracking-{1}'.format(resource_type, self.target_node_name)
        return self.call(
            topic, server, 'QueryStatus', timeout=timeout, retry=retry,
            QualifierJson=resource_qualifier_json)

    def add_resource_status_listener(self, resource_type, status_handler=None):
        if not status_handler:
            status_handler = NotificationHandlerBase()

        topic='{0}-Event-{1}'.format(resource_type, self.broker_name)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        endpoints = [NotificationServiceClient.ListenerEndpoint(status_handler)]

        super(NotificationServiceClient, self).add_listener(
            topic, server, endpoints)
        return True

    def remove_resource_status_listener(self, resource_type):
        topic='{0}-Event-{1}'.format(resource_type, self.broker_name)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        super(NotificationServiceClient, self).remove_listener(
            topic, server)
        pass

    def is_listening_on_resource(self, resource_type):
        topic='{0}-Event-{1}'.format(resource_type, self.broker_name)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        return super(NotificationServiceClient, self).is_listening(
            topic, server)

    def is_broker_ip(self, broker_pod_ip):
        return self.broker_pod_ip == broker_pod_ip
