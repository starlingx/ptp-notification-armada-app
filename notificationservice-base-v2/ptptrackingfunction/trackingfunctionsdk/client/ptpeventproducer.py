#
# Copyright (c) 2021-2024 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import json
import time
import oslo_messaging
from oslo_config import cfg

from trackingfunctionsdk.client.base import BrokerClientBase

import logging

LOG = logging.getLogger(__name__)

from trackingfunctionsdk.common.helpers import log_helper, constants

log_helper.config_logger(LOG)


class PtpEventProducer(object):
    class ListenerEndpoint(object):
        target = oslo_messaging.Target(namespace='notification', version='1.0')

        def __init__(self, handler=None):

            self.handler = handler
            self.init_time = time.time()
            pass

        def QueryStatus(self, ctx, **rpc_kwargs):
            # This is where the "GET" commands run through
            LOG.info("PtpEventProducer QueryStatus called %s" % rpc_kwargs)
            if self.handler:
                return self.handler.query_status(**rpc_kwargs)
            else:
                return None

        def TriggerDelivery(self, ctx, **rpc_kwargs):
            LOG.debug("PtpEventProducer TriggerDelivery called %s" % rpc_kwargs)
            if self.handler:
                return self.handler.trigger_delivery(**rpc_kwargs)
            else:
                return None

    def __init__(self, node_name, local_broker_transport_endpoint,
                 registration_broker_transport_endpoint=None):
        self.Id = id(self)
        self.node_name = node_name
        self.local_broker_client = BrokerClientBase(
            'LocalPtpEventProducer', local_broker_transport_endpoint)
        if registration_broker_transport_endpoint:
            self.registration_broker_client = BrokerClientBase(
                'AllPtpEventProducer', registration_broker_transport_endpoint)
        else:
            self.registration_broker_client = None
        return

    def __del__(self):
        if self.local_broker_client:
            del self.local_broker_client
            self.local_broker_client = None
        if self.registration_broker_client:
            del self.registration_broker_client
            self.registration_broker_client = None
        return

    def publish_status(self, ptpstatus, retry=3):
        result = False
        result1 = self.publish_status_local(ptpstatus,
                                            retry) if self.local_broker_client else result
        result2 = self.publish_status_all(ptpstatus,
                                          retry) if self.registration_broker_client else result
        return result1, result2

    def publish_status_local(self, ptpstatus, source, retry=3):
        if not self.local_broker_client:
            return False
        topic = '{0}-Event-v2-{1}'.format(source, self.node_name)
        server = None
        isretrystopped = False
        while not isretrystopped:
            try:
                self.local_broker_client.cast(
                    topic, 'NotifyStatus', notification=ptpstatus)
                LOG.debug("Published ptp status local:{0}@Topic:{1}".format(ptpstatus, topic))
                break
            except Exception as ex:
                LOG.warning("Failed to publish ptp status local:{0}@Topic:{1} due to: {2}".format(
                    ptpstatus, topic, str(ex)))
                retry = retry - 1
                isretrystopped = False if retry > 0 else True

        if isretrystopped:
            LOG.error("Failed to publish ptp status local:{0}@Topic:{1}".format(
                ptpstatus, topic))
        return isretrystopped == False

    def publish_status_all(self, ptpstatus, retry=3):
        if not self.registration_broker_client:
            return False
        topic_all = 'PTP-Event-v2-*'
        server = None
        isretrystopped = False
        while not isretrystopped:
            try:
                self.registration_broker_client.cast(
                    topic_all, 'NotifyStatus', notification=ptpstatus)
                LOG.debug("Published ptp status all:{0}@Topic:{1}".format(ptpstatus, topic_all))
                break
            except Exception as ex:
                LOG.warning("Failed to publish ptp status all:{0}@Topic:{1} due to: {2}".format(
                    ptpstatus, topic_all, str(ex)))
                retry = retry - 1
                isretrystopped = False if retry > 0 else True

        if isretrystopped:
            LOG.error("Failed to publish ptp status all:{0}@Topic:{1}".format(
                ptpstatus, topic_all))
        return isretrystopped == False

    def start_status_listener(self, handler=None):
        result = False
        result1 = self.start_status_listener_local(handler) if self.local_broker_client else result
        result2 = self.start_status_listener_all(
            handler) if self.registration_broker_client else result
        result = result1 and result2
        return result

    def start_status_listener_local(self, handler=None):
        if not self.local_broker_client:
            return False

        topic = 'PTP-Status-v2'
        server = 'PTP-Tracking-{0}'.format(self.node_name)
        endpoints = [PtpEventProducer.ListenerEndpoint(handler)]

        self.local_broker_client.add_listener(
            topic, server, endpoints)
        return True

    def start_status_listener_all(self, handler=None):
        if not self.registration_broker_client:
            return False

        topic = 'PTP-Status-v2'
        server = 'PTP-Tracking-{0}'.format(self.node_name)
        endpoints = [PtpEventProducer.ListenerEndpoint(handler)]

        self.registration_broker_client.add_listener(
            topic, server, endpoints)
        return True

    def stop_status_listener(self):
        result = False
        result1 = self.stop_status_listener_local() if self.local_broker_client else result
        result2 = self.stop_status_listener_all() if self.registration_broker_client else result
        result = result1 and result2
        return result

    def stop_status_listener_local(self):
        if not self.local_broker_client:
            return False

        topic = 'PTP-Status-v2'
        server = "PTP-Tracking-{0}".format(self.node_name)
        self.local_broker_client.remove_listener(
            topic, server)

    def stop_status_listener_all(self):
        if not self.registration_broker_client:
            return False

        topic = 'PTP-Status-v2'
        server = "PTP-Tracking-{0}".format(self.node_name)
        self.registration_broker_client.remove_listener(
            topic, server)

    def is_listening(self):
        result = False
        result1 = self.is_listening_local() if self.local_broker_client else result
        result2 = self.is_listening_all() if self.registration_broker_client else result
        result = result1 and result2
        return result

    def is_listening_local(self):
        if not self.local_broker_client:
            return False

        topic = 'PTP-Status-v2'
        server = "PTP-Tracking-{0}".format(self.node_name)
        return self.local_broker_client.is_listening(
            topic, server)

    def is_listening_all(self):
        if not self.registration_broker_client:
            return False
        topic = 'PTP-Status-v2'
        server = "PTP-Tracking-{0}".format(self.node_name)
        return self.registration_broker_client.is_listening(
            topic, server)
