#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import json
import logging
import os
import time

import oslo_messaging
from locationservicesdk.client.base import BrokerClientBase
from locationservicesdk.common.helpers import log_helper
from oslo_config import cfg

LOG = logging.getLogger(__name__)

log_helper.config_logger(LOG)


class LocationProducer(BrokerClientBase):
    class ListenerEndpoint(object):
        target = oslo_messaging.Target(namespace='notification', version='1.0')

        def __init__(self, location_info, handler=None):
            self.location_info = location_info
            self.handler = handler
            pass

        def QueryLocation(self, ctx, **rpc_kwargs):
            LOG.debug("LocationProducer QueryLocation called %s" % rpc_kwargs)
            return self.location_info

        def TriggerAnnouncement(self, ctx, **rpc_kwargs):
            LOG.debug("LocationProducer TriggerAnnouncement called %s" %
                      rpc_kwargs)
            if self.handler:
                return self.handler.handle(**rpc_kwargs)
            else:
                return False

    def __init__(self, node_name, registrationservice_transport_endpoint):
        self.Id = id(self)
        self.node_name = node_name
        super(LocationProducer, self).__init__(
            'locationproducer', registrationservice_transport_endpoint)
        return

    def __del__(self):
        super(LocationProducer, self).__del__()
        return

    def announce_location(self, LocationInfo):
        location_topic_all = 'LocationListener-*'
        location_topic = 'LocationListener-{0}'.format(self.node_name)
        server = None
        while True:
            try:
                self.cast(location_topic_all, 'NotifyLocation',
                          location_info=LocationInfo)
                LOG.debug(
                    "Broadcast location info:{0}@Topic:{1}".format(LocationInfo, location_topic))
            except Exception as ex:
                LOG.debug(
                    "Failed to publish location due to: {0}".format(str(ex)))
                continue
            else:
                break

    def start_location_listener(self, location_info, handler=None):

        topic = 'LocationQuery'
        server = "LocationService-{0}".format(self.node_name)
        endpoints = [LocationProducer.ListenerEndpoint(location_info, handler)]

        super(LocationProducer, self).add_listener(
            topic, server, endpoints)
        return True

    def stop_location_listener(self):
        topic = 'LocationQuery'
        server = "LocationService-{0}".format(self.node_name)
        super(LocationProducer, self).remove_listener(
            topic, server)

    def is_listening(self):
        topic = 'LocationQuery'
        server = "LocationService-{0}".format(self.node_name)
        return super(LocationProducer, self).is_listening(
            topic, server)
