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

from notificationclientsdk.common.helpers import hostfile_helper

from notificationclientsdk.client.base import BrokerClientBase

from notificationclientsdk.client.notificationservice import NotificationServiceClient, NotificationHandlerBase

import logging

LOG = logging.getLogger(__name__)

from notificationclientsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

class LocationHandlerBase(object):

    def __init__(self):
        self.NOTIFICATIONSERVICE_HOSTNAME = 'notificationservice-{0}'
        pass

    def handle(self, location_info):
        pass

class LocationHandlerDefault(LocationHandlerBase):
    def __init__(self, host_file_path='/etc/hosts'):
        self.hostfile = host_file_path
        super(LocationHandlerDefault, self).__init__()

    def handle(self, location_info):
        LOG.debug("Received location info:{0}".format(location_info))
        nodename = location_info.get('NodeName', None)
        podip = location_info.get("PodIP", None)
        if not nodename or not podip:
            LOG.warning("Mising NodeName or PodIP inside location info")
            return False

        hostfile_helper.update_host(
            self.NOTIFICATIONSERVICE_HOSTNAME.format(nodename),
            podip)
        LOG.debug("Updated location with IP:{0}".format(podip))
        return True

class LocationServiceClient(BrokerClientBase):
    class ListenerEndpoint(object):
        target = oslo_messaging.Target(namespace='notification', version='1.0')

        def __init__(self, handler):
            self.handler = handler

        def NotifyLocation(self, ctx, location_info):
            LOG.debug("LocationServiceClient NotifyLocation called %s" % location_info)
            self.handler.handle(location_info)
            return time.time()

    def __init__(self, registrationservice_transport_endpoint):
        self.Id = id(self)
        super(LocationServiceClient, self).__init__(
            'locationservice', registrationservice_transport_endpoint)
        return

    def __del__(self):
        super(LocationServiceClient, self).__del__()
        return

    def update_location(self, target_node_name, location_handler=None, timeout=None, retry=None):
        if not location_handler:
            location_handler = LocationHandlerDefault('/etc/hosts')
        location_info = self.query_location(target_node_name, timeout=timeout, retry=retry)
        if location_info:
            location_handler.handle(location_info)
            return True
        else:
            return False

    def query_location(self, target_node_name, timeout=None, retry=None):
        topic = 'LocationQuery'
        server = 'LocationService-{0}'.format(target_node_name)
        return self.call(topic, server, 'QueryLocation', timeout=timeout, retry=retry)

    def trigger_location_annoucement(self, timeout=None, retry=None):
        topic = 'LocationQuery'
        return self.cast(topic, 'TriggerAnnouncement', timeout=timeout, retry=retry)

    def add_location_listener(self, target_node_name, location_handler=None):
        if not location_handler:
            location_handler = LocationHandlerDefault('/etc/hosts')

        topic='LocationListener-{0}'.format(target_node_name)
        server="LocationListener-{0}".format(self.Id)
        endpoints = [LocationServiceClient.ListenerEndpoint(location_handler)]

        super(LocationServiceClient, self).add_listener(
            topic, server, endpoints)
        return True

    def remove_location_listener(self, target_node_name):
        topic='LocationListener-{0}'.format(target_node_name)
        server="LocationListener-{0}".format(self.Id)
        super(LocationServiceClient, self).remove_listener(
            topic, server)

    def is_listening_on_location(self, target_node_name):
        topic='LocationListener-{0}'.format(target_node_name)
        server="LocationListener-{0}".format(self.Id)
        return super(LocationServiceClient, self).is_listening(
            topic, server)

    ### extensions
    def trigger_publishing_status(self, resource_type,
        timeout=None, retry=None, resource_qualifier_json=None):
        topic = '{0}-Status'.format(resource_type)
        try:
            self.cast(
                topic, 'TriggerDelivery', timeout=timeout, retry=retry,
                QualifierJson=resource_qualifier_json)
        except Exception as ex:
            LOG.warning("Fail to trigger_publishing_status: {0}".format(str(ex)))
            return False
        return True

    def add_resource_status_listener(self, resource_type, status_handler=None):
        if not status_handler:
            status_handler = NotificationHandlerBase()

        topic='{0}-Event-*'.format(resource_type)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        endpoints = [NotificationServiceClient.ListenerEndpoint(status_handler)]

        super(LocationServiceClient, self).add_listener(
            topic, server, endpoints)
        return True

    def remove_resource_status_listener(self, resource_type):
        topic='{0}-Event-*'.format(resource_type)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        super(LocationServiceClient, self).remove_listener(
            topic, server)
        pass

    def is_listening_on_resource(self, resource_type):
        topic='{0}-Event-*'.format(resource_type)
        server="{0}-EventListener-{1}".format(resource_type, self.Id)
        return super(LocationServiceClient, self).is_listening(
            topic, server)
