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
import logging

import multiprocessing as mp
import threading

from trackingfunctionsdk.common.helpers import rpc_helper
from trackingfunctionsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from trackingfunctionsdk.model.dto.resourcetype import ResourceType
from trackingfunctionsdk.model.dto.ptpstate import PtpState

from trackingfunctionsdk.client.ptpeventproducer import PtpEventProducer

from trackingfunctionsdk.common.helpers import ptpsync as ptpsync

LOG = logging.getLogger(__name__)

from trackingfunctionsdk.common.helpers import log_helper
log_helper.config_logger(LOG)

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME",'controller-0')


'''Entry point of Default Process Worker'''
def ProcessWorkerDefault(event, sqlalchemy_conf_json, broker_transport_endpoint):
    worker = PtpWatcherDefault(event, sqlalchemy_conf_json, broker_transport_endpoint)
    worker.run()
    return


class PtpWatcherDefault:
    DEFAULT_PTPTRACKER_CONTEXT = {
        'holdover_seconds': 30,
        'poll_freq_seconds': 2
    }

    class PtpRequestHandlerDefault(object):
        def __init__(self, watcher):
            self.watcher = watcher
            self.init_time = time.time()

        def query_status(self, **rpc_kwargs):
            self.watcher.ptptracker_context_lock.acquire()
            sync_state = self.watcher.ptptracker_context.get('sync_state', PtpState.Freerun)
            last_event_time = self.watcher.ptptracker_context.get('last_event_time', time.time())
            self.watcher.ptptracker_context_lock.release()

            lastStatus = {
                'ResourceType': ResourceType.TypePTP,
                'EventData': {
                    'State': sync_state
                },
                'ResourceQualifier': {
                    'NodeName': self.watcher.node_name
                },
                'EventTimestamp': last_event_time
            }
            return lastStatus

        def trigger_delivery(self, **rpc_kwargs):
            self.watcher.forced_publishing = True
            self.watcher.signal_ptp_event()
            pass

    def __init__(self, event, sqlalchemy_conf_json, daemon_context_json):
        self.sqlalchemy_conf = json.loads(sqlalchemy_conf_json)
        self.event = event
        self.init_time = time.time()

        self.daemon_context = json.loads(daemon_context_json)
        self.ptptracker_context = self.daemon_context.get(
            'ptptracker_context', PtpWatcherDefault.DEFAULT_PTPTRACKER_CONTEXT)
        self.ptptracker_context['sync_state'] = PtpState.Freerun
        self.ptptracker_context['last_event_time'] = self.init_time
        self.ptptracker_context_lock = threading.Lock()

        self.ptp_device_simulated = "true" == self.ptptracker_context.get('device_simulated', "False").lower()

        self.event_timeout = float(self.ptptracker_context['poll_freq_seconds'])

        self.node_name = self.daemon_context['THIS_NODE_NAME']
        self.namespace = self.daemon_context.get('THIS_NAMESPACE', 'notification')

        broker_transport_endpoint = self.daemon_context['NOTIFICATION_TRANSPORT_ENDPOINT']

        registration_transport_endpoint = self.daemon_context['REGISTRATION_TRANSPORT_ENDPOINT']

        self.broker_endpoint = RpcEndpointInfo(broker_transport_endpoint)
        self.registration_broker_endpoint = RpcEndpointInfo(registration_transport_endpoint)
        self.ptpeventproducer = PtpEventProducer(
            self.node_name,
            self.broker_endpoint.TransportEndpoint,
            self.registration_broker_endpoint.TransportEndpoint)

        self.__ptprequest_handler = PtpWatcherDefault.PtpRequestHandlerDefault(self)
        self.forced_publishing = False

    def signal_ptp_event(self):
        if self.event:
            self.event.set()
        else:
            LOG.warning("Unable to assert ptp event")
            pass

    def run(self):
        # start location listener
        self.__start_listener()
        while True:
            # annouce the location
            forced = self.forced_publishing
            self.forced_publishing = False
            self.__publish_ptpstatus(forced)
            if self.event.wait(self.event_timeout):
                LOG.debug("daemon control event is asserted")
                self.event.clear()
            else:
                LOG.debug("daemon control event is timeout")
                pass
            continue
        self.__stop_listener()

    '''Start listener to answer querying from clients'''
    def __start_listener(self):
        LOG.debug("start listener to answer location querying")

        self.ptpeventproducer.start_status_listener(
            self.__ptprequest_handler
            )
        return

    def __stop_listener(self):
        LOG.debug("stop listener to answer location querying")

        self.ptpeventproducer.stop_status_listener(self.location_info)
        return

    def __get_ptp_status(self, holdover_time, freq, sync_state, last_event_time):
        new_event = False
        new_event_time = last_event_time
        if self.ptp_device_simulated:
            now = time.time()
            timediff = now - last_event_time
            if timediff > holdover_time:
                new_event = True
                new_event_time = now
                if sync_state == PtpState.Freerun:
                    sync_state = PtpState.Locked
                elif sync_state == PtpState.Locked:
                    sync_state = PtpState.Holdover
                elif sync_state == PtpState.Holdover:
                    sync_state = PtpState.Freerun
                else:
                    sync_state = PtpState.Freerun
        else:
            new_event, sync_state, new_event_time = ptpsync.ptp_status(
                holdover_time, freq, sync_state, last_event_time)
        return new_event, sync_state, new_event_time

    '''announce location'''
    def __publish_ptpstatus(self, forced=False):
        holdover_time = float(self.ptptracker_context['holdover_seconds'])
        freq = float(self.ptptracker_context['poll_freq_seconds'])
        sync_state = self.ptptracker_context.get('sync_state', 'Unknown')
        last_event_time = self.ptptracker_context.get('last_event_time', time.time())

        new_event, sync_state, new_event_time = self.__get_ptp_status(
            holdover_time, freq, sync_state, last_event_time)

        if new_event or forced:
            # update context
            self.ptptracker_context_lock.acquire()
            self.ptptracker_context['sync_state'] = sync_state
            self.ptptracker_context['last_event_time'] = new_event_time
            self.ptptracker_context_lock.release()

            # publish new event
            LOG.debug("publish ptp status to clients")
            lastStatus = {
                'ResourceType': 'PTP',
                'EventData': {
                    'State': sync_state
                },
                'ResourceQualifier': {
                    'NodeName': self.node_name
                },
                'EventTimestamp': new_event_time
            }
            self.ptpeventproducer.publish_status(lastStatus)
        return


class DaemonControl(object):

    def __init__(self, sqlalchemy_conf_json, daemon_context_json, process_worker = None):
        self.event = mp.Event()
        self.daemon_context = json.loads(daemon_context_json)
        self.node_name = self.daemon_context['THIS_NODE_NAME']
        if not process_worker:
            process_worker = ProcessWorkerDefault

        self. sqlalchemy_conf_json = sqlalchemy_conf_json
        self.daemon_context_json = daemon_context_json
        self.process_worker = process_worker
        return

    def refresh(self):
        self.process_worker(self.event, self.sqlalchemy_conf_json, self.daemon_context_json)
        self.event.set()
