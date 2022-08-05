#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import datetime
import json
import logging
import multiprocessing as mp
import os
import sys
import threading
import time
from oslo_utils import uuidutils

from trackingfunctionsdk.client.ptpeventproducer import PtpEventProducer
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import ptpsync
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers.dmesg_watcher import DmesgWatcher
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.model.dto.overallclockstate import OverallClockState
from trackingfunctionsdk.model.dto.resourcetype import ResourceType
from trackingfunctionsdk.model.dto.rpc_endpoint import RpcEndpointInfo

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", 'controller-0')

# Event source to event type mapping
source_type = {
    '/sync/gnss-status/gnss-sync-status': 'event.sync.gnss-status.gnss-state-change',
    '/sync/ptp-status/clock-class': 'event.sync.ptp-status.ptp-clock-class-change',
    '/sync/ptp-status/lock-state': 'event.sync.ptp-status.ptp-state-change',
    '/sync/sync-status/os-clock-sync-state': 'event.sync.sync-status.os-clock-sync-state-change',
    '/sync/sync-status/sync-state': 'event.sync.sync-status.synchronization-state-change',
    '/sync/synce-status/clock-quality': 'event.sync.synce-status.synce-clock-quality-change',
    '/sync/synce-status/lock-state-extended': 'event.sync.synce-status.synce-state-change-extended',
    '/sync/synce-status/lock-state': 'event.sync.synce-status.synce-state-change',
    '/sync/synce-status/lock-state': 'event.sync.synce-status.synce-state-change',
}

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

    DEFAULT_GNSSTRACKER_CONTEXT = {
        'holdover_seconds': 30,
        'poll_freq_seconds': 2
    }

    DEFAULT_OS_CLOCK_TRACKER_CONTEXT = {
        'holdover_seconds': 30,
        'poll_freq_seconds': 2
    }

    DEFAULT_OVERALL_SYNC_TRACKER_CONTEXT = {
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

            resource_address = rpc_kwargs.get('ResourceAddress', None)
            if resource_address:
                _, nodename, resource_path = ptpsync.parse_resource_address(resource_address)
                lastStatus = {
                    'id': uuidutils.generate_uuid(),
                    'specversion': constants.SPEC_VERSION,
                    'source': resource_path,
                    'type': source_type[resource_path],
                    'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(last_event_time)),
                    'data': {
                        'version': constants.DATA_VERSION,
                        'values': [
                            {
                                'data_type': constants.DATA_TYPE_NOTIFICATION,
                                'ResourceAddress': resource_address,
                                'value_type': constants.VALUE_TYPE_ENUMERATION,
                                'value': sync_state
                            }
                        ]
                    }
                }
            else:
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

        self.gnsstracker_context = self.daemon_context.get(
            'gnsstracker_context', PtpWatcherDefault.DEFAULT_GNSSTRACKER_CONTEXT)
        self.gnsstracker_context['sync_state'] = GnssState.Freerun
        self.gnsstracker_context['last_event_time'] = self.init_time
        self.gnsstracker_context_lock = threading.Lock()

        self.osclocktracker_context = self.daemon_context.get(
            'os_clock_tracker_context', PtpWatcherDefault.DEFAULT_OS_CLOCK_TRACKER_CONTEXT)
        self.osclocktracker_context['sync_state'] = OsClockState.Freerun
        self.osclocktracker_context['last_event_time'] = self.init_time
        self.osclocktracker_context_lock = threading.Lock()

        self.overalltracker_context = self.daemon_context.get(
            'overall_sync_tracker_context', PtpWatcherDefault.DEFAULT_OVERALL_SYNC_TRACKER_CONTEXT)
        self.overalltracker_context['sync_state'] = OverallClockState.Freerun
        self.overalltracker_context['last_event_time'] = self.init_time
        self.overalltracker_context_lock = threading.Lock()

        self.ptp_device_simulated = "true" == self.ptptracker_context.get('device_simulated',
                                                                          "False")

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

        self.watcher = DmesgWatcher()
        self.observer_list = [GnssMonitor(i) for i in self.daemon_context['GNSS_CONFIGS']]
        for observer in self.observer_list:
            self.watcher.attach(observer)

        self.watcher_thread = threading.Thread(target=self.watcher.run_watcher)

        # Setup OS Clock monitor
        self.os_clock_monitor = OsClockMonitor(phc2sys_config=self.daemon_context['PHC2SYS_CONFIG']) 

    def signal_ptp_event(self):
        if self.event:
            self.event.set()
        else:
            LOG.warning("Unable to assert ptp event")
            pass

    def run(self):
        # start location listener
        self.__start_listener()

        # start GNSS monitoring
        self.watcher_thread.start()

        while True:
            # announce the location
            forced = self.forced_publishing
            self.forced_publishing = False
            self.__publish_ptpstatus(forced)
            self.__publish_os_clock_status(forced)
            self.__publish_gnss_status(forced)
            self.__publish_overall_sync_status(forced)
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

    def __get_gnss_status(self, holdover_time, freq, sync_state, last_event_time, gnss_monitor):
        new_event, sync_state, new_event_time = gnss_monitor.get_gnss_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.debug("Getting GNSS status.")
        return new_event, sync_state, new_event_time

    def __get_os_clock_status(self, holdover_time, freq, sync_state, last_event_time):
        new_event, sync_state, new_event_time = self.os_clock_monitor.os_clock_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.debug("Getting os clock status.")
        return new_event, sync_state, new_event_time

    def __get_overall_sync_state(self, holdover_time, freq, sync_state, last_event_time):
        new_event = False
        new_event_time = last_event_time
        previous_sync_state = sync_state
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = round(current_time - last_event_time)
        max_holdover_time = (holdover_time - freq * 2)
        gnss_state = None
        os_clock_state = None
        ptp_state = None

        LOG.debug("Getting overall sync state.")
        for gnss in self.observer_list:
            if gnss._state == GnssState.Holdover or gnss._state == GnssState.Freerun:
                gnss_state = GnssState.Freerun
            elif gnss._state == GnssState.Locked and gnss_state != GnssState.Freerun:
                gnss_state = GnssState.Locked

        os_clock_state = self.os_clock_monitor.get_os_clock_state()

        ptp_state = self.ptptracker_context.get('sync_state')

        if gnss_state is GnssState.Freerun or os_clock_state is OsClockState.Freerun or ptp_state\
                is PtpState.Freerun:
            sync_state = OverallClockState.Freerun
        else:
            sync_state = OverallClockState.Locked

        if sync_state == OverallClockState.Freerun:
            if previous_sync_state in [constants.UNKNOWN_PHC_STATE, constants.FREERUN_PHC_STATE]:
                sync_state = OverallClockState.Freerun
            elif previous_sync_state == constants.LOCKED_PHC_STATE:
                sync_state = OverallClockState.Holdover
            elif previous_sync_state == constants.HOLDOVER_PHC_STATE and \
                    time_in_holdover < max_holdover_time:
                sync_state = OverallClockState.Holdover
            else:
                sync_state = OverallClockState.Freerun

        if sync_state != previous_sync_state:
            new_event = True
            new_event_time = datetime.datetime.utcnow().timestamp()
        return new_event, sync_state, new_event_time

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

    def __publish_os_clock_status(self, forced=False):
        holdover_time = float(self.osclocktracker_context['holdover_seconds'])
        freq = float(self.osclocktracker_context['poll_freq_seconds'])
        sync_state = self.osclocktracker_context.get('sync_state', 'Unknown')
        last_event_time = self.osclocktracker_context.get('last_event_time', time.time())

        new_event, sync_state, new_event_time = self.__get_os_clock_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.debug("Got os clock status.")

        if new_event or forced:
            self.osclocktracker_context_lock.acquire()
            self.osclocktracker_context['sync_state'] = sync_state
            self.osclocktracker_context['last_event_time'] = new_event_time
            self.osclocktracker_context_lock.release()

            LOG.debug("Publish OS Clock Status")
            lastStatus = {
                'ResourceType': 'OS Clock',
                'EventData': {
                    'State': sync_state
                },
                'ResourceQualifier': {
                    'NodeName': self.node_name
                },
                'EventTimestamp': new_event_time
            }
            # publish new event in API version v2 format
            resource_address = ptpsync.format_resource_address(
                self.node_name, constants.SOURCE_SYNC_OS_CLOCK)
            lastStatus = {
                'id': uuidutils.generate_uuid(),
                'specversion': constants.SPEC_VERSION,
                'source': constants.SOURCE_SYNC_OS_CLOCK,
                'type': source_type[constants.SOURCE_SYNC_OS_CLOCK],
                'time': new_event_time,
                'data': {
                    'version': constants.DATA_VERSION,
                    'values': [
                        {
                            'data_type': constants.DATA_TYPE_NOTIFICATION,
                            'ResourceAddress': resource_address,
                            'value_type': constants.VALUE_TYPE_ENUMERATION,
                            'value': sync_state
                        }
                    ]
                }
            }
            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_OS_CLOCK)
            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_ALL)
            return

    def __publish_overall_sync_status(self, forced=False):
        holdover_time = float(self.overalltracker_context['holdover_seconds'])
        freq = float(self.overalltracker_context['poll_freq_seconds'])
        sync_state = self.overalltracker_context.get('sync_state', 'Unknown')
        last_event_time = self.overalltracker_context.get('last_event_time', time.time())

        new_event, sync_state, new_event_time = self.__get_overall_sync_state(
            holdover_time, freq, sync_state, last_event_time)

        if new_event or forced:
            # Update context
            self.overalltracker_context_lock.acquire()
            self.overalltracker_context['sync_state'] = sync_state
            self.overalltracker_context['last_event_time'] = new_event_time
            self.overalltracker_context_lock.release()

            LOG.debug("Publish overall sync status.")
            resource_address = ptpsync.format_resource_address(
                self.node_name, constants.SOURCE_SYNC_SYNC_STATE)
            lastStatus = {
                'id': uuidutils.generate_uuid(),
                'specversion': constants.SPEC_VERSION,
                'source': constants.SOURCE_SYNC_SYNC_STATE,
                'type': source_type[constants.SOURCE_SYNC_SYNC_STATE],
                'time': new_event_time,
                'data': {
                    'version': constants.DATA_VERSION,
                    'values': [
                        {
                            'data_type': constants.DATA_TYPE_NOTIFICATION,
                            'ResourceAddress': resource_address,
                            'value_type': constants.VALUE_TYPE_ENUMERATION,
                            'value': sync_state
                        }
                    ]
                }
            }

            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_SYNC_STATE)
            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_ALL)

    def __publish_gnss_status(self, forced=False):
        holdover_time = float(self.gnsstracker_context['holdover_seconds'])
        freq = float(self.gnsstracker_context['poll_freq_seconds'])
        sync_state = self.gnsstracker_context.get('sync_state', 'Unknown')
        last_event_time = self.gnsstracker_context.get('last_event_time', time.time())
        LOG.debug("GNSS sync_state %s" % sync_state)

        for gnss in self.observer_list:
            new_event, sync_state, new_event_time = self.__get_gnss_status(
                holdover_time, freq, sync_state, last_event_time, gnss)

            if new_event or forced:
                # update context
                self.gnsstracker_context_lock.acquire()
                self.gnsstracker_context['sync_state'] = sync_state
                self.gnsstracker_context['last_event_time'] = new_event_time
                self.gnsstracker_context_lock.release()

                LOG.debug("Publish GNSS status.")

                # publish new event in API version v2 format
                resource_address = ptpsync.format_resource_address(
                    self.node_name, constants.SOURCE_SYNC_GNSS_SYNC_STATUS)
                lastStatus = {
                    'id': uuidutils.generate_uuid(),
                    'specversion': constants.SPEC_VERSION,
                    'source': constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                    'type': source_type[constants.SOURCE_SYNC_GNSS_SYNC_STATUS],
                    'time': new_event_time,
                    'data': {
                        'version': constants.DATA_VERSION,
                        'values': [
                            {
                                'data_type': constants.DATA_TYPE_NOTIFICATION,
                                'ResourceAddress': resource_address,
                                'value_type': constants.VALUE_TYPE_ENUMERATION,
                                'value': sync_state
                            }
                        ]
                    }
                }
                self.ptpeventproducer.publish_status(lastStatus,
                                                     constants.SOURCE_SYNC_GNSS_SYNC_STATUS)
                self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_ALL)
        return

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
            LOG.debug("Publish ptp status to clients")
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
            self.ptpeventproducer.publish_status(lastStatus, 'PTP')

            # publish new event in API version v2 format
            resource_address = ptpsync.format_resource_address(
                self.node_name, constants.SOURCE_SYNC_PTP_LOCK_STATE)
            lastStatus = {
                'id': uuidutils.generate_uuid(),
                'specversion': constants.SPEC_VERSION,
                'source': constants.SOURCE_SYNC_PTP_LOCK_STATE,
                'type': source_type[constants.SOURCE_SYNC_PTP_LOCK_STATE],
                'time': new_event_time,
                'data': {
                    'version': constants.DATA_VERSION,
                    'values': [
                        {
                            'data_type': constants.DATA_TYPE_NOTIFICATION,
                            'ResourceAddress': resource_address,
                            'value_type': constants.VALUE_TYPE_ENUMERATION,
                            'value': sync_state
                        }
                    ]
                }
            }
            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_PTP_LOCK_STATE)
            self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_ALL)
        return


class DaemonControl(object):

    def __init__(self, sqlalchemy_conf_json, daemon_context_json, process_worker=None):
        self.event = mp.Event()
        self.daemon_context = json.loads(daemon_context_json)
        self.node_name = self.daemon_context['THIS_NODE_NAME']
        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.sqlalchemy_conf_json = sqlalchemy_conf_json
        self.daemon_context_json = daemon_context_json
        self.process_worker = process_worker
        return

    def refresh(self):
        self.process_worker(self.event, self.sqlalchemy_conf_json, self.daemon_context_json)
        self.event.set()
