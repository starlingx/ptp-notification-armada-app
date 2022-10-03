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
import threading
import time
from oslo_utils import uuidutils

from trackingfunctionsdk.client.ptpeventproducer import PtpEventProducer
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor
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
        def __init__(self, watcher, daemon_context):
            self.watcher = watcher
            self.init_time = time.time()
            self.daemon_context = daemon_context

        def _build_event_response(self, resource_path, last_event_time, resource_address,
                                  sync_state, value_type=constants.VALUE_TYPE_ENUMERATION):
            if resource_path in [constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                                 constants.SOURCE_SYNCE_CLOCK_QUALITY]:
                data_type = constants.DATA_TYPE_METRIC
            else:
                data_type = constants.DATA_TYPE_NOTIFICATION
            lastStatus = {
                'id': uuidutils.generate_uuid(),
                'specversion': constants.SPEC_VERSION,
                'source': resource_path,
                'type': source_type[resource_path],
                'time': last_event_time,
                'data': {
                    'version': constants.DATA_VERSION,
                    'values': [
                        {
                            'data_type': data_type,
                            'ResourceAddress': resource_address,
                            'value_type': value_type,
                            'value': sync_state
                        }
                    ]
                }
            }
            return lastStatus

        def query_status(self, **rpc_kwargs):
            lastStatus = {}
            resource_address = rpc_kwargs.get('ResourceAddress', None)
            optional = rpc_kwargs.get('optional', None)
            if resource_address:
                _, nodename, resource_path = utils.parse_resource_address(resource_address)
                if resource_path == constants.SOURCE_SYNC_ALL:
                    resource_path = constants.SOURCE_SYNC_SYNC_STATE
                if resource_path == constants.SOURCE_SYNC_GNSS_SYNC_STATUS:
                    self.watcher.gnsstracker_context_lock.acquire()
                    if optional:
                        sync_state = self.watcher.gnsstracker_context[optional]. \
                            get('sync_state', GnssState.Failure_Nofix)
                        last_event_time = self.watcher.gnsstracker_context[optional].get(
                            'last_event_time',
                            time.time())
                        lastStatus[optional] = self._build_event_response(resource_path,
                                                                          last_event_time,
                                                                          resource_address,
                                                                          sync_state)
                    else:
                        for config in self.daemon_context['GNSS_INSTANCES']:
                            sync_state = self.watcher.gnsstracker_context[config] \
                                .get('sync_state', GnssState.Failure_Nofix)
                            last_event_time = self.watcher.gnsstracker_context[config].get(
                                'last_event_time',
                                time.time())
                            lastStatus[config] = self._build_event_response(resource_path,
                                                                            last_event_time,
                                                                            resource_address,
                                                                            sync_state)
                    self.watcher.gnsstracker_context_lock.release()
                elif resource_path == constants.SOURCE_SYNC_PTP_CLOCK_CLASS:
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional:
                        clock_class = self.watcher.ptptracker_context[optional].get('clock_class',
                                                                                    '248')
                        last_clock_class_event_time = self.watcher.ptptracker_context[optional].get(
                            'last_clock_class_event_time',
                            time.time())
                        lastStatus[optional] = \
                            self._build_event_response(resource_path,
                                                       last_clock_class_event_time,
                                                       resource_address,
                                                       clock_class,
                                                       constants.VALUE_TYPE_METRIC)
                    else:
                        for config in self.daemon_context['PTP4L_INSTANCES']:
                            clock_class = self.watcher.ptptracker_context[config].get('clock_class',
                                                                                      '248')
                            last_clock_class_event_time = \
                                self.watcher.ptptracker_context[config].get(
                                    'last_clock_class_event_time',
                                    time.time())
                            lastStatus[config] = \
                                self._build_event_response(resource_path,
                                                           last_clock_class_event_time,
                                                           resource_address,
                                                           clock_class,
                                                           constants.VALUE_TYPE_METRIC)
                    self.watcher.ptptracker_context_lock.release()
                elif resource_path == constants.SOURCE_SYNC_PTP_LOCK_STATE:
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional:
                        sync_state = self.watcher.ptptracker_context[optional].get('sync_state',
                                                                                   PtpState.Freerun)
                        last_event_time = self.watcher.ptptracker_context[optional].get(
                            'last_event_time',
                            time.time())
                        lastStatus[optional] = self._build_event_response(resource_path,
                                                                          last_event_time,
                                                                          resource_address,
                                                                          sync_state)
                    else:
                        for config in self.daemon_context['PTP4L_INSTANCES']:
                            sync_state = \
                                self.watcher.ptptracker_context[config].get('sync_state',
                                                                            PtpState.Freerun)
                            last_event_time = self.watcher.ptptracker_context[config].get(
                                'last_event_time',
                                time.time())
                            lastStatus[config] = self._build_event_response(resource_path,
                                                                            last_event_time,
                                                                            resource_address,
                                                                            sync_state)
                    self.watcher.ptptracker_context_lock.release()

                elif resource_path == constants.SOURCE_SYNC_OS_CLOCK:
                    self.watcher.osclocktracker_context_lock.acquire()
                    sync_state = self.watcher.osclocktracker_context.get('sync_state',
                                                                         OsClockState.Freerun)
                    last_event_time = self.watcher.osclocktracker_context.get('last_event_time',
                                                                              time.time())
                    self.watcher.osclocktracker_context_lock.release()
                    lastStatus['os_clock_status'] = self._build_event_response(resource_path,
                                                                               last_event_time,
                                                                               resource_address,
                                                                               sync_state)
                elif resource_path == constants.SOURCE_SYNC_SYNC_STATE:
                    self.watcher.overalltracker_context_lock.acquire()
                    sync_state = self.watcher.overalltracker_context.get('sync_state',
                                                                         OverallClockState.Freerun)
                    last_event_time = self.watcher.overalltracker_context.get('last_event_time',
                                                                              time.time())
                    self.watcher.overalltracker_context_lock.release()
                    lastStatus['overall_sync_status'] = self._build_event_response(resource_path,
                                                                                   last_event_time,
                                                                                   resource_address,
                                                                                   sync_state)
                LOG.debug("query_status: {}".format(lastStatus))
            else:
                # Request is for PTP v1 notification
                # PTP v1 only supports single instance ptp
                instance = self.daemon_context['PTP4L_INSTANCES'][0]
                if len(self.daemon_context['PTP4L_INSTANCES']) > 1:
                    LOG.warning(
                        "Multiple ptp4l instances configured, retrieving status for %s" % instance)
                self.watcher.ptptracker_context_lock.acquire()
                sync_state = self.watcher.ptptracker_context[instance].get('sync_state',
                                                                           PtpState.Freerun)
                last_event_time = self.watcher.ptptracker_context[instance].get('last_event_time',
                                                                                time.time())
                lastStatus[constants.PTP_V1_KEY] = {
                    'ResourceType': ResourceType.TypePTP,
                    'EventData': {
                        'State': sync_state
                    },
                    'ResourceQualifier': {
                        'NodeName': self.watcher.node_name
                    },
                    'EventTimestamp': last_event_time
                }
                self.watcher.ptptracker_context_lock.release()
                LOG.warning("query_status PTP v1: {}".format(lastStatus))

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

        # PTP Context
        self.ptptracker_context = {}
        for config in self.daemon_context['PTP4L_INSTANCES']:
            self.ptptracker_context[config] = PtpWatcherDefault.DEFAULT_PTPTRACKER_CONTEXT.copy()
            self.ptptracker_context[config]['sync_state'] = PtpState.Freerun
            self.ptptracker_context[config]['last_event_time'] = self.init_time
            self.ptptracker_context[config]['holdover_seconds'] = os.environ.get("PTP_HOLDOVER_SECONDS", 30)
            self.ptptracker_context[config]['poll_freq_seconds'] = os.environ.get(
                "CONTROL_TIMEOUT", 2)
            self.ptp_device_simulated = "true" == self.ptptracker_context[config].get(
                'device_simulated',
                "False")
            self.ptptracker_context_lock = threading.Lock()
        LOG.debug("ptptracker_context: %s" % self.ptptracker_context)

        # GNSS Context
        self.gnsstracker_context = {}
        for config in self.daemon_context['GNSS_INSTANCES']:
            self.gnsstracker_context[config] = PtpWatcherDefault.DEFAULT_GNSSTRACKER_CONTEXT.copy()
            self.gnsstracker_context[config]['sync_state'] = GnssState.Failure_Nofix
            self.gnsstracker_context[config]['last_event_time'] = self.init_time
            self.gnsstracker_context[config]['holdover_seconds'] = os.environ.get("GNSS_HOLDOVER_SECONDS", 30)
            self.gnsstracker_context[config]['poll_freq_seconds'] = os.environ.get(
                "CONTROL_TIMEOUT", 2)
            self.gnsstracker_context_lock = threading.Lock()
        LOG.debug("gnsstracker_context: %s" % self.gnsstracker_context)

        # OS Clock Context
        self.osclocktracker_context = {}
        self.osclocktracker_context = PtpWatcherDefault.DEFAULT_OS_CLOCK_TRACKER_CONTEXT.copy()
        self.osclocktracker_context['sync_state'] = OsClockState.Freerun
        self.osclocktracker_context['last_event_time'] = self.init_time
        self.osclocktracker_context['holdover_seconds'] = os.environ.get("OS_CLOCK_HOLDOVER_SECONDS", 30)
        self.osclocktracker_context['poll_freq_seconds'] = os.environ.get(
                "CONTROL_TIMEOUT", 2)
        self.osclocktracker_context_lock = threading.Lock()

        # Overall Sync Context
        self.overalltracker_context = {}
        self.overalltracker_context = PtpWatcherDefault.DEFAULT_OVERALL_SYNC_TRACKER_CONTEXT.copy()
        self.overalltracker_context['sync_state'] = OverallClockState.Freerun
        self.overalltracker_context['last_event_time'] = self.init_time
        self.overalltracker_context['holdover_seconds'] = os.environ.get("OVERALL_HOLDOVER_SECONDS", 30)
        self.overalltracker_context['poll_freq_seconds'] = os.environ.get(
                "CONTROL_TIMEOUT", 2)
        self.overalltracker_context_lock = threading.Lock()

        self.event_timeout = float(os.environ.get('CONTROL_TIMEOUT', 2))

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

        self.__ptprequest_handler = PtpWatcherDefault.PtpRequestHandlerDefault(self,
                                                                               self.daemon_context)

        # Set forced_publishing to True so that initial states are published
        # Main loop in run() sets it to false after the first iteration
        self.forced_publishing = True

        self.observer_list = [GnssMonitor(i) for i in self.daemon_context['GNSS_CONFIGS']]

        # Setup OS Clock monitor
        self.os_clock_monitor = OsClockMonitor(phc2sys_config=self.daemon_context['PHC2SYS_CONFIG'])

        # Setup PTP Monitor(s)
        self.ptp_monitor_list = [
            PtpMonitor(config, self.ptptracker_context[config]['holdover_seconds'],
                       self.ptptracker_context[config]['poll_freq_seconds'],
                       self.daemon_context['PHC2SYS_SERVICE_NAME']) for config in
            self.daemon_context['PTP4L_INSTANCES']]

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
            # announce the location
            forced = self.forced_publishing
            self.forced_publishing = False
            if self.ptptracker_context:
                self.__publish_ptpstatus(forced)
            if self.gnsstracker_context:
                self.__publish_gnss_status(forced)
            self.__publish_os_clock_status(forced)
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
        time_in_holdover = None
        if previous_sync_state == constants.HOLDOVER_PHC_STATE:
            time_in_holdover = round(current_time - last_event_time)
        max_holdover_time = (holdover_time - freq * 2)
        gnss_state = None
        os_clock_state = None
        ptp_state = None

        LOG.debug("Getting overall sync state.")
        for gnss in self.observer_list:
            if gnss._state == constants.UNKNOWN_PHC_STATE or gnss._state == GnssState.Failure_Nofix:
                gnss_state = GnssState.Failure_Nofix
            elif gnss._state == GnssState.Synchronized and gnss_state != GnssState.Failure_Nofix:
                gnss_state = GnssState.Synchronized

        for ptp4l in self.ptp_monitor_list:
            _, read_state, _ = ptp4l.get_ptp_sync_state()
            if read_state == PtpState.Holdover or read_state == PtpState.Freerun or \
                    read_state == constants.UNKNOWN_PHC_STATE:
                ptp_state = PtpState.Freerun
            elif read_state == PtpState.Locked and ptp_state != PtpState.Freerun:
                ptp_state = PtpState.Locked

        os_clock_state = self.os_clock_monitor.get_os_clock_state()

        if gnss_state is GnssState.Failure_Nofix or os_clock_state is OsClockState.Freerun or \
                ptp_state is PtpState.Freerun:
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
                LOG.debug("Overall sync: Time in holdover is %s  Max time in holdover is %s" % (
                    time_in_holdover, max_holdover_time))
                sync_state = OverallClockState.Holdover
            else:
                sync_state = OverallClockState.Freerun

        if sync_state != previous_sync_state:
            new_event = True
            new_event_time = datetime.datetime.utcnow().timestamp()
        return new_event, sync_state, new_event_time

    def __get_ptp_status(self, holdover_time, freq, sync_state, last_event_time, ptp_monitor):
        new_event = False
        new_event_time = last_event_time
        ptp_monitor.set_ptp_sync_state()
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
            new_event, sync_state, new_event_time = ptp_monitor.get_ptp_sync_state()
        return new_event, sync_state, new_event_time

    '''announce location'''

    def __publish_os_clock_status(self, forced=False):
        holdover_time = float(self.osclocktracker_context['holdover_seconds'])
        freq = float(self.osclocktracker_context['poll_freq_seconds'])
        sync_state = self.osclocktracker_context.get('sync_state', 'Unknown')
        last_event_time = self.osclocktracker_context.get('last_event_time', time.time())
        lastStatus = {}

        new_event, sync_state, new_event_time = self.__get_os_clock_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.info("os_clock_status: state is %s, new_event is %s " % (sync_state, new_event))
        if new_event or forced:
            self.osclocktracker_context_lock.acquire()
            self.osclocktracker_context['sync_state'] = sync_state
            self.osclocktracker_context['last_event_time'] = new_event_time
            self.osclocktracker_context_lock.release()

            LOG.debug("Publish OS Clock Status")
            # publish new event in API version v2 format
            resource_address = utils.format_resource_address(
                self.node_name, constants.SOURCE_SYNC_OS_CLOCK)
            lastStatus['os_clock_status'] = {
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
        lastStatus = {}
        holdover_time = float(self.overalltracker_context['holdover_seconds'])
        freq = float(self.overalltracker_context['poll_freq_seconds'])
        sync_state = self.overalltracker_context.get('sync_state', 'Unknown')
        last_event_time = self.overalltracker_context.get('last_event_time', time.time())

        new_event, sync_state, new_event_time = self.__get_overall_sync_state(
            holdover_time, freq, sync_state, last_event_time)
        LOG.info("overall_sync_state: state is %s, new_event is %s " % (sync_state, new_event))

        if new_event or forced:
            # Update context
            self.overalltracker_context_lock.acquire()
            self.overalltracker_context['sync_state'] = sync_state
            self.overalltracker_context['last_event_time'] = new_event_time
            self.overalltracker_context_lock.release()

            LOG.debug("Publish overall sync status.")
            resource_address = utils.format_resource_address(
                self.node_name, constants.SOURCE_SYNC_SYNC_STATE)
            lastStatus['overall_sync_status'] = {
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
        lastStatus = {}
        for gnss in self.observer_list:
            holdover_time = float(
                self.gnsstracker_context[gnss.ts2phc_service_name]['holdover_seconds'])
            freq = float(self.gnsstracker_context[gnss.ts2phc_service_name]['poll_freq_seconds'])
            sync_state = self.gnsstracker_context[gnss.ts2phc_service_name].get('sync_state',
                                                                                'Unknown')
            last_event_time = self.gnsstracker_context[gnss.ts2phc_service_name].get(
                'last_event_time',
                time.time())

            new_event, sync_state, new_event_time = self.__get_gnss_status(
                holdover_time, freq, sync_state, last_event_time, gnss)
            LOG.info("%s gnss_status: state is %s, new_event is %s" % (
            gnss.ts2phc_service_name, sync_state, new_event))

            if new_event or forced:
                # update context
                self.gnsstracker_context_lock.acquire()
                self.gnsstracker_context[gnss.ts2phc_service_name]['sync_state'] = sync_state
                self.gnsstracker_context[gnss.ts2phc_service_name][
                    'last_event_time'] = new_event_time
                self.gnsstracker_context_lock.release()

                LOG.debug("Publish GNSS status.")

                # publish new event in API version v2 format
                resource_address = utils.format_resource_address(
                    self.node_name, constants.SOURCE_SYNC_GNSS_SYNC_STATUS)
                lastStatus[gnss.ts2phc_service_name] = {
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
        lastStatus = {}
        lastClockClassStatus = {}
        for ptp_monitor in self.ptp_monitor_list:
            holdover_time = \
                float(self.ptptracker_context[ptp_monitor.ptp4l_service_name]['holdover_seconds'])
            freq = float(
                self.ptptracker_context[ptp_monitor.ptp4l_service_name]['poll_freq_seconds'])
            sync_state = self.ptptracker_context[ptp_monitor.ptp4l_service_name]. \
                get('sync_state', 'Unknown')
            last_event_time = self.ptptracker_context[ptp_monitor.ptp4l_service_name] \
                .get('last_event_time', time.time())

            new_event, sync_state, new_event_time = self.__get_ptp_status(
                holdover_time, freq, sync_state, last_event_time, ptp_monitor)
            LOG.info("%s PTP sync state: state is %s, new_event is %s" % (
                ptp_monitor.ptp4l_service_name, sync_state, new_event))

            new_clock_class_event, clock_class, clock_class_event_time = \
                ptp_monitor.get_ptp_clock_class()
            LOG.info("%s PTP clock class: clockClass is %s, new_event is %s" % (
                ptp_monitor.ptp4l_service_name, clock_class, new_clock_class_event))
            if new_event or forced:
                # update context
                self.ptptracker_context_lock.acquire()
                self.ptptracker_context[ptp_monitor.ptp4l_service_name]['sync_state'] = sync_state
                self.ptptracker_context[ptp_monitor.ptp4l_service_name][
                    'last_event_time'] = new_event_time

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
                lastStatus = {}
                # publish new event in API version v2 format
                resource_address = utils.format_resource_address(
                    self.node_name, constants.SOURCE_SYNC_PTP_LOCK_STATE)
                lastStatus[ptp_monitor.ptp4l_service_name] = {
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
                self.ptptracker_context_lock.release()
                self.ptpeventproducer.publish_status(lastStatus,
                                                     constants.SOURCE_SYNC_PTP_LOCK_STATE)
                self.ptpeventproducer.publish_status(lastStatus, constants.SOURCE_SYNC_ALL)

            if new_clock_class_event or forced:
                # update context
                self.ptptracker_context_lock.acquire()
                self.ptptracker_context[ptp_monitor.ptp4l_service_name]['clock_class'] = clock_class
                self.ptptracker_context[ptp_monitor.ptp4l_service_name][
                    'last_clock_class_event_time'] \
                    = clock_class_event_time


                resource_address = utils.format_resource_address(
                    self.node_name, constants.SOURCE_SYNC_PTP_CLOCK_CLASS)

                lastClockClassStatus[ptp_monitor.ptp4l_service_name] = {
                    'id': uuidutils.generate_uuid(),
                    'specversion': constants.SPEC_VERSION,
                    'source': constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                    'type': source_type[constants.SOURCE_SYNC_PTP_CLOCK_CLASS],
                    'time': clock_class_event_time,
                    'data': {
                        'version': constants.DATA_VERSION,
                        'values': [
                            {
                                'data_type': constants.DATA_TYPE_NOTIFICATION,
                                'ResourceAddress': resource_address,
                                'value_type': constants.VALUE_TYPE_METRIC,
                                'value': clock_class
                            }
                        ]
                    }
                }
                self.ptptracker_context_lock.release()
                LOG.info("Publishing clockClass for %s: %s" % (ptp_monitor.ptp4l_service_name,
                                                               clock_class))
                self.ptpeventproducer.publish_status(lastClockClassStatus,
                                                     constants.SOURCE_SYNC_PTP_CLOCK_CLASS)
                self.ptpeventproducer.publish_status(lastClockClassStatus,
                                                     constants.SOURCE_SYNC_ALL)

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
