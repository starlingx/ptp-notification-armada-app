#
# Copyright (c) 2021-2025 Wind River Systems, Inc.
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
from trackingfunctionsdk.common.helpers import constants, log_helper
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.model.dto.overallclockstate import OverallClockState
from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.model.dto.resourcetype import ResourceType
from trackingfunctionsdk.model.dto.rpc_endpoint import RpcEndpointInfo
from trackingfunctionsdk.services.health import HealthServer

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

THIS_NODE_NAME = os.environ.get("THIS_NODE_NAME", 'controller-0')

# Event source to event type mapping
source_type = {
    '/sync/gnss-status/gnss-sync-status':
        'event.sync.gnss-status.gnss-state-change',
    '/sync/ptp-status/clock-class':
        'event.sync.ptp-status.ptp-clock-class-change',
    '/sync/ptp-status/lock-state':
        'event.sync.ptp-status.ptp-state-change', 
    '/sync/sync-status/os-clock-sync-state':
        'event.sync.sync-status.os-clock-sync-state-change',
    '/sync/sync-status/sync-state':
        'event.sync.sync-status.synchronization-state-change',
    '/sync/synce-status/clock-quality':
        'event.sync.synce-status.synce-clock-quality-change',
    '/sync/synce-status/lock-state-extended':
        'event.sync.synce-status.synce-state-change-extended',
    '/sync/synce-status/lock-state':
        'event.sync.synce-status.synce-state-change',
}

'''Entry point of Default Process Worker'''


def ProcessWorkerDefault(event, sqlalchemy_conf_json,
                         broker_transport_endpoint):
    worker = PtpWatcherDefault(event, sqlalchemy_conf_json,
                               broker_transport_endpoint)
    worker.run()


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

        def _build_event_response(
            self, resource_path, last_event_time, resource_address,
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
                            'value': sync_state.upper()
                        }
                    ]
                }
            }
            return lastStatus

        def query_status(self, **rpc_kwargs):
            # Client PULL status requests come through here
            # Dict is used for legacy notification format
            lastStatus = {}
            # List is used for standard notification format
            newStatus = []

            resource_address = rpc_kwargs.get('ResourceAddress', None)
            optional = rpc_kwargs.get('optional', None)
            if resource_address:
                _, nodename, resource_path = utils.parse_resource_address(
                    resource_address)
                if resource_path == constants.SOURCE_SYNC_GNSS_SYNC_STATUS or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.gnsstracker_context_lock.acquire()
                    if optional and self.watcher.gnsstracker_context.get(optional):
                        sync_state = \
                            self.watcher.gnsstracker_context[optional].get(
                                'sync_state', GnssState.Failure_Nofix)
                        last_event_time = \
                            self.watcher.gnsstracker_context[optional].get(
                                'last_event_time', time.time())
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                            last_event_time,
                            utils.format_resource_address(nodename,
                                constants.SOURCE_SYNC_GNSS_SYNC_STATUS, optional),
                            sync_state)
                        newStatus.append(lastStatus[optional])
                    elif not optional:
                        for config in self.daemon_context['GNSS_INSTANCES']:
                            sync_state = \
                                self.watcher.gnsstracker_context[config].get(
                                    'sync_state', GnssState.Failure_Nofix)
                            last_event_time = \
                                self.watcher.gnsstracker_context[config].get(
                                    'last_event_time', time.time())
                            lastStatus[config] = self._build_event_response(
                                constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                                last_event_time,
                                utils.format_resource_address(nodename,
                                    constants.SOURCE_SYNC_GNSS_SYNC_STATUS, config),
                                sync_state)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.gnsstracker_context_lock.release()
                if resource_path == constants.SOURCE_SYNC_PTP_CLOCK_CLASS or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional and self.watcher.ptptracker_context.get(optional):
                        clock_class = \
                            self.watcher.ptptracker_context[optional].get(
                                'clock_class', '248')
                        last_clock_class_event_time = \
                            self.watcher.ptptracker_context[optional].get(
                                'last_clock_class_event_time', time.time())
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                            last_clock_class_event_time,
                            utils.format_resource_address(nodename,
                                constants.SOURCE_SYNC_PTP_CLOCK_CLASS, optional),
                            clock_class, constants.VALUE_TYPE_METRIC)
                        newStatus.append(lastStatus[optional])
                    elif not optional:
                        for config in self.daemon_context['PTP4L_INSTANCES']:
                            clock_class = \
                                self.watcher.ptptracker_context[config].get(
                                    'clock_class', '248')
                            last_clock_class_event_time = \
                                self.watcher.ptptracker_context[config].get(
                                    'last_clock_class_event_time',
                                    time.time())
                            lastStatus[config] = self._build_event_response(
                                constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                                last_clock_class_event_time,
                                utils.format_resource_address(nodename,
                                    constants.SOURCE_SYNC_PTP_CLOCK_CLASS, config),
                                clock_class, constants.VALUE_TYPE_METRIC)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.ptptracker_context_lock.release()
                if resource_path == constants.SOURCE_SYNC_PTP_LOCK_STATE or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional and self.watcher.ptptracker_context.get(optional):
                        sync_state = \
                            self.watcher.ptptracker_context[optional].get(
                                'sync_state', PtpState.Freerun)
                        last_event_time = \
                            self.watcher.ptptracker_context[optional].get(
                                'last_event_time', time.time())
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_PTP_LOCK_STATE,
                            last_event_time,
                            utils.format_resource_address(nodename,
                                constants.SOURCE_SYNC_PTP_LOCK_STATE, optional),
                            sync_state)
                        newStatus.append(lastStatus[optional])
                    elif not optional:
                        for config in self.daemon_context['PTP4L_INSTANCES']:
                            sync_state = \
                                self.watcher.ptptracker_context[config].get(
                                    'sync_state', PtpState.Freerun)
                            last_event_time = \
                                self.watcher.ptptracker_context[config].get(
                                    'last_event_time', time.time())
                            lastStatus[config] = self._build_event_response(
                                constants.SOURCE_SYNC_PTP_LOCK_STATE,
                                last_event_time,
                                utils.format_resource_address(nodename,
                                    constants.SOURCE_SYNC_PTP_LOCK_STATE, config),
                                sync_state)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.ptptracker_context_lock.release()

                if resource_path == constants.SOURCE_SYNC_OS_CLOCK or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.osclocktracker_context_lock.acquire()
                    sync_state = \
                        self.watcher.osclocktracker_context.get(
                            'sync_state', OsClockState.Freerun)
                    last_event_time = \
                        self.watcher.osclocktracker_context.get(
                            'last_event_time', time.time())
                    self.watcher.osclocktracker_context_lock.release()
                    lastStatus['os_clock_status'] = self._build_event_response(
                        constants.SOURCE_SYNC_OS_CLOCK, last_event_time,
                        utils.format_resource_address(nodename,
                            constants.SOURCE_SYNC_OS_CLOCK),
                        sync_state)
                    newStatus.append(lastStatus['os_clock_status'])
                if resource_path == constants.SOURCE_SYNC_SYNC_STATE or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.overalltracker_context_lock.acquire()
                    sync_state = self.watcher.overalltracker_context.get(
                        'sync_state', OverallClockState.Freerun)
                    last_event_time = self.watcher.overalltracker_context.get(
                        'last_event_time', time.time())
                    self.watcher.overalltracker_context_lock.release()
                    lastStatus['overall_sync_status'] = \
                        self._build_event_response(
                            constants.SOURCE_SYNC_SYNC_STATE, last_event_time,
                            utils.format_resource_address(nodename,
                                constants.SOURCE_SYNC_SYNC_STATE),
                            sync_state)
                    if resource_path == constants.SOURCE_SYNC_ALL:
                        newStatus.append(lastStatus['overall_sync_status'])
                    else:
                        # Special handling for overall_sync_status
                        # There will only ever be a single response from
                        # SOURCE_SYNC_SYNC_STATE.
                        # Return a dict rather than a list
                        newStatus = lastStatus['overall_sync_status']


            if constants.NOTIFICATION_FORMAT == 'standard':
                LOG.info("PULL status returning: %s", newStatus)
                return newStatus
            else:
                LOG.info("PULL status returning: {}".format(lastStatus))
                return lastStatus


        def trigger_delivery(self, **rpc_kwargs):
            self.watcher.forced_publishing = True
            self.watcher.signal_ptp_event()

    def __init__(self, event, sqlalchemy_conf_json, daemon_context_json):
        self.sqlalchemy_conf = json.loads(sqlalchemy_conf_json)
        self.event = event
        self.init_time = time.time()

        self.daemon_context = json.loads(daemon_context_json)

        # PTP Context
        self.ptptracker_context = {}
        for config in self.daemon_context['PTP4L_INSTANCES']:
            self.ptptracker_context[config] = \
                PtpWatcherDefault.DEFAULT_PTPTRACKER_CONTEXT.copy()
            self.ptptracker_context[config]['sync_state'] = PtpState.Freerun
            self.ptptracker_context[config]['last_event_time'] = self.init_time
            self.ptptracker_context[config]['holdover_seconds'] = \
                os.environ.get("PTP_HOLDOVER_SECONDS", 30)
            self.ptptracker_context[config]['poll_freq_seconds'] = \
                os.environ.get("CONTROL_TIMEOUT", 2)
            self.ptp_device_simulated = \
                "true" == self.ptptracker_context[config].get(
                    'device_simulated', "False")
        self.ptptracker_context_lock = threading.Lock()
        LOG.debug("ptptracker_context: %s" % self.ptptracker_context)

        # GNSS Context
        self.gnsstracker_context = {}
        for config in self.daemon_context['GNSS_INSTANCES']:
            self.gnsstracker_context[config] = \
                PtpWatcherDefault.DEFAULT_GNSSTRACKER_CONTEXT.copy()
            self.gnsstracker_context[config]['sync_state'] = \
                GnssState.Failure_Nofix
            self.gnsstracker_context[config]['last_event_time'] = \
                self.init_time
            self.gnsstracker_context[config]['holdover_seconds'] = \
                os.environ.get("GNSS_HOLDOVER_SECONDS", 30)
            self.gnsstracker_context[config]['poll_freq_seconds'] = \
                os.environ.get("CONTROL_TIMEOUT", 2)
        self.gnsstracker_context_lock = threading.Lock()
        LOG.debug("gnsstracker_context: %s" % self.gnsstracker_context)

        # OS Clock Context
        self.osclocktracker_context = {}
        self.osclocktracker_context = \
            PtpWatcherDefault.DEFAULT_OS_CLOCK_TRACKER_CONTEXT.copy()
        self.osclocktracker_context['sync_state'] = OsClockState.Freerun
        self.osclocktracker_context['last_event_time'] = self.init_time
        self.osclocktracker_context['holdover_seconds'] = \
            os.environ.get("OS_CLOCK_HOLDOVER_SECONDS", 30)
        self.osclocktracker_context['poll_freq_seconds'] = \
            os.environ.get("CONTROL_TIMEOUT", 2)
        self.osclocktracker_context_lock = threading.Lock()

        # Overall Sync Context
        self.overalltracker_context = {}
        self.overalltracker_context = \
            PtpWatcherDefault.DEFAULT_OVERALL_SYNC_TRACKER_CONTEXT.copy()
        self.overalltracker_context['sync_state'] = OverallClockState.Freerun
        self.overalltracker_context['last_event_time'] = self.init_time
        self.overalltracker_context['holdover_seconds'] = \
            os.environ.get("OVERALL_HOLDOVER_SECONDS", 30)
        self.overalltracker_context['poll_freq_seconds'] = \
            os.environ.get("CONTROL_TIMEOUT", 2)
        self.overalltracker_context_lock = threading.Lock()

        self.event_timeout = float(os.environ.get('CONTROL_TIMEOUT', 2))

        self.node_name = self.daemon_context['THIS_NODE_NAME']

        self.namespace = self.daemon_context.get(
            'THIS_NAMESPACE', 'notification')

        broker_transport_endpoint = \
            self.daemon_context['NOTIFICATION_TRANSPORT_ENDPOINT']

        registration_transport_endpoint = \
            self.daemon_context['REGISTRATION_TRANSPORT_ENDPOINT']

        self.broker_endpoint = RpcEndpointInfo(broker_transport_endpoint)
        self.registration_broker_endpoint = \
            RpcEndpointInfo(registration_transport_endpoint)
        self.ptpeventproducer = PtpEventProducer(
            self.node_name,
            self.broker_endpoint.TransportEndpoint,
            self.registration_broker_endpoint.TransportEndpoint)

        self.__ptprequest_handler = \
            PtpWatcherDefault.PtpRequestHandlerDefault(
                self, self.daemon_context)

        # Set forced_publishing to True so that initial states are published
        # Main loop in run() sets it to false after the first iteration
        self.forced_publishing = True

        self.observer_list = [
            GnssMonitor(i) for i in self.daemon_context['GNSS_CONFIGS']]

        # Setup OS Clock monitor
        self.os_clock_monitor = OsClockMonitor(
            phc2sys_config=self.daemon_context['PHC2SYS_CONFIG'])

        # Setup PTP Monitor(s)
        self.ptp_monitor_list = [
            PtpMonitor(config,
                       self.ptptracker_context[config]['holdover_seconds'],
                       self.ptptracker_context[config]['poll_freq_seconds'],
                       self.daemon_context['PHC2SYS_SERVICE_NAME'])
            for config in self.daemon_context['PTP4L_INSTANCES']]

    def signal_ptp_event(self):
        if self.event:
            self.event.set()
        else:
            LOG.warning("Unable to assert ptp event")

    def run(self):
        # start location listener
        self.__start_listener()

        # Start the server for k8s httpGet health checks
        notificationservice_health = HealthServer()
        notificationservice_health.run()

        # Need to give the notificationclient sidecar pods
        # a few seconds to re-connect to the newly started
        # RabbitMQ. If we don't wait here, the initial
        # status delivieries can be sent before the clients
        # are connected and they will never receive the
        # notification
        # This approach can probably be improved by
        # checking the RabbitMQ endpoint
        time.sleep(10)

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
            continue
        self.__stop_listener()

    '''Start listener to answer querying from clients'''

    def __start_listener(self):
        LOG.debug("start listener to answer location querying")

        self.ptpeventproducer.start_status_listener(
            self.__ptprequest_handler
        )

    def __stop_listener(self):
        LOG.debug("stop listener to answer location querying")

        self.ptpeventproducer.stop_status_listener(self.location_info)

    def __get_gnss_status(self, holdover_time, freq, sync_state,
                          last_event_time, gnss_monitor):
        new_event, sync_state, new_event_time = gnss_monitor.get_gnss_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.debug("Getting GNSS status.")
        return new_event, sync_state, new_event_time

    def __get_os_clock_status(self, holdover_time, freq, sync_state,
                              last_event_time):
        new_event, sync_state, new_event_time = \
            self.os_clock_monitor.os_clock_status(
                holdover_time, freq, sync_state, last_event_time)
        LOG.debug("Getting os clock status.")
        return new_event, sync_state, new_event_time

    def __get_primary_ptp_state(self, ptp_device):
        # The PTP device itself is being disciplined or not ?
        # Check which ptp4l instance disciplining this PTP device
        # disciplining source could be either GNSS or PTP
        primary_ptp4l = None
        ptp_state = PtpState.Freerun
        for ptp4l in self.ptp_monitor_list:
            # runtime loading of ptp4l config
            ptp4l.set_ptp_devices()
            if (
                ptp_device in ptp4l.get_ptp_devices()
                and ptp4l.get_ptp_sync_source() != constants.ClockSourceType.TypeNA
            ):
                primary_ptp4l = ptp4l
                break

        if primary_ptp4l is not None:
            _, read_state, _ = primary_ptp4l.get_ptp_sync_state()
            if read_state == PtpState.Locked:
                ptp_state = PtpState.Locked

        return primary_ptp4l, ptp_state

    def __get_primary_gnss_state(self, ptp_device):
        # The PTP device itself is being disciplined or not ?
        # Check which ts2phc instance disciplining this PTP device
        primary_gnss = None
        gnss_state = GnssState.Failure_Nofix
        for gnss in self.observer_list:
            # runtime loading of ts2phc config
            gnss.set_ptp_devices()
            if ptp_device in gnss.get_ptp_devices():
                primary_gnss = gnss
                break

        if primary_gnss is not None:
            read_state = primary_gnss._state
            if read_state == GnssState.Synchronized:
                gnss_state = GnssState.Synchronized

        return primary_gnss, gnss_state

    def __get_overall_sync_state(
        self, holdover_time, freq, sync_state, last_event_time
    ):
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

        # overall state depends on os_clock_state and single chained gnss/ptp state
        # Need to figure out which gnss/ptp is disciplining the PHC that syncs os_clock
        os_clock_state = self.os_clock_monitor.get_os_clock_state()
        sync_state = OverallClockState.Freerun
        chaining_info = (
            f"Overall sync state chaining info:\n"
            f"os-clock-state = {os_clock_state}"
        )
        if os_clock_state is not OsClockState.Freerun:
            # PTP device that is disciplining the OS clock,
            # valid even for HA source devices
            ptp_device = self.os_clock_monitor.get_source_ptp_device()
            if ptp_device is None:
                # This may happen in virtualized environments
                LOG.warning("No PTP device. Defaulting overall state Freerun")
                chaining_info += (
                    f"\nos-clock's source ptp-device = None"
                )
            else:
                # What source (gnss or ptp) disciplining the PTP device at the
                # moment (A PTP device could have both TS2PHC/gnss source and
                # PTP4l/slave)
                sync_source = constants.ClockSourceType.TypeNA
                # any ts2phc instance disciplining the ptp device (source GNSS)
                primary_gnss, gnss_state = self.__get_primary_gnss_state(ptp_device)
                if primary_gnss is not None:
                    sync_source = constants.ClockSourceType.TypeGNSS

                # any ptp4l instance disciplining the ptp device (source PTP or GNSS)
                primary_ptp4l, ptp_state = self.__get_primary_ptp_state(ptp_device)

                # which source: PTP or GNSS
                # In presence of ptp4l instance disciplining the ptp device, it truly
                # dictates what source it is using.
                if primary_ptp4l is not None:
                    sync_source = primary_ptp4l.get_ptp_sync_source()

                ptp4l_instance_and_state = (
                    "NA"
                    if primary_ptp4l is None
                    else (primary_ptp4l.ptp4l_service_name, ptp_state)
                )
                ts2phc_instance_and_state = (
                    "NA"
                    if primary_gnss is None
                    else (primary_gnss.ts2phc_service_name, gnss_state)
                )
                chaining_info += (
                    f"\nos-clock's source ptp-device = {ptp_device}\n"
                    f"ptp-device's sync-source = {sync_source}\n"
                    f"(PTP source) ptp4l-instance-and-state = {ptp4l_instance_and_state}\n"
                    f"(GNSS source) ts2phc-instance-and-state = {ts2phc_instance_and_state}"
                )

                # Based on sync_source that is used to discipline the ptp device,
                # dependent ts2phc or ptp4l instance's state is chosen.
                if sync_source == constants.ClockSourceType.TypeNA:
                    # The PTP device is not being disciplined by any PTP4l/TS2PHC instances
                    LOG.warning(
                        "PTP device used by PHC2SYS is not synced/configured on any PTP4l/TS2PHC instances."
                    )

                elif (
                    sync_source == constants.ClockSourceType.TypeGNSS
                    and gnss_state is GnssState.Synchronized
                ):
                    sync_state = OverallClockState.Locked

                elif (
                    sync_source == constants.ClockSourceType.TypePTP
                    and ptp_state is PtpState.Locked
                ):
                    sync_state = OverallClockState.Locked

        if sync_state == OverallClockState.Freerun:
            if previous_sync_state in [
                constants.UNKNOWN_PHC_STATE,
                constants.FREERUN_PHC_STATE,
            ]:
                sync_state = OverallClockState.Freerun
            elif previous_sync_state == constants.LOCKED_PHC_STATE:
                sync_state = OverallClockState.Holdover
            elif (
                previous_sync_state == constants.HOLDOVER_PHC_STATE
                and time_in_holdover < max_holdover_time
            ):
                LOG.debug(
                    "Overall sync: Time in holdover is %s "
                    "Max time in holdover is %s" % (time_in_holdover, max_holdover_time)
                )
                sync_state = OverallClockState.Holdover
            else:
                sync_state = OverallClockState.Freerun

        chaining_info += (
            f"\nOverall sync: previous-state = {previous_sync_state}, new-state = {sync_state}"
        )

        if sync_state != previous_sync_state:
            new_event = True
            new_event_time = datetime.datetime.utcnow().timestamp()
            LOG.info(chaining_info)
        else:
            LOG.debug(chaining_info)
        return new_event, sync_state, new_event_time

    def __get_ptp_status(self, holdover_time, freq, sync_state,
                         last_event_time, ptp_monitor):
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
            new_event, sync_state, new_event_time = \
                ptp_monitor.get_ptp_sync_state()
        return new_event, sync_state, new_event_time

    '''announce location'''

    def __publish_os_clock_status(self, forced=False):
        holdover_time = float(self.osclocktracker_context['holdover_seconds'])
        freq = float(self.osclocktracker_context['poll_freq_seconds'])
        sync_state = self.osclocktracker_context.get('sync_state', 'Unknown')
        last_event_time = self.osclocktracker_context.get('last_event_time',
                                                          time.time())
        lastStatus = {}
        newStatus = []

        new_event, sync_state, new_event_time = self.__get_os_clock_status(
            holdover_time, freq, sync_state, last_event_time)
        LOG.info("os_clock_status: state is %s, new_event is %s "
                 % (sync_state, new_event))
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
                            'value': sync_state.upper()
                        }
                    ]
                }
            }

            newStatus.append(lastStatus['os_clock_status'])

            if constants.NOTIFICATION_FORMAT == 'standard':
                self.ptpeventproducer.publish_status(
                    newStatus, constants.SOURCE_SYNC_OS_CLOCK)
                self.ptpeventproducer.publish_status(
                    newStatus, constants.SOURCE_SYNC_ALL)
            else:
                self.ptpeventproducer.publish_status(
                    lastStatus, constants.SOURCE_SYNC_OS_CLOCK)
                self.ptpeventproducer.publish_status(
                    lastStatus, constants.SOURCE_SYNC_ALL)

    def __publish_overall_sync_status(self, forced=False):
        lastStatus = {}
        newStatus = []
        holdover_time = float(self.overalltracker_context['holdover_seconds'])
        freq = float(self.overalltracker_context['poll_freq_seconds'])
        sync_state = self.overalltracker_context.get('sync_state', 'Unknown')
        last_event_time = self.overalltracker_context.get('last_event_time',
                                                          time.time())

        new_event, sync_state, new_event_time = self.__get_overall_sync_state(
            holdover_time, freq, sync_state, last_event_time)
        LOG.info("overall_sync_state: state is %s, new_event is %s "
                 % (sync_state, new_event))

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
                            'value': sync_state.upper()
                        }
                    ]
                }
            }
            newStatus.append(lastStatus['overall_sync_status'])
            if constants.NOTIFICATION_FORMAT == 'standard':
                self.ptpeventproducer.publish_status(
                    newStatus, constants.SOURCE_SYNC_SYNC_STATE)
                self.ptpeventproducer.publish_status(
                    newStatus, constants.SOURCE_SYNC_ALL)
            else:
                self.ptpeventproducer.publish_status(
                    lastStatus, constants.SOURCE_SYNC_SYNC_STATE)
                self.ptpeventproducer.publish_status(
                    lastStatus, constants.SOURCE_SYNC_ALL)   

    def __publish_gnss_status(self, forced=False):

        for gnss in self.observer_list:
            # Ensure that status structs are cleared between each iteration
            lastStatus = {}
            newStatus = []
            holdover_time = float(
                self.gnsstracker_context[
                    gnss.ts2phc_service_name]['holdover_seconds'])
            freq = float(self.gnsstracker_context[
                gnss.ts2phc_service_name]['poll_freq_seconds'])
            sync_state = \
                self.gnsstracker_context[gnss.ts2phc_service_name].get(
                    'sync_state', 'Unknown')
            last_event_time = \
                self.gnsstracker_context[gnss.ts2phc_service_name].get(
                    'last_event_time', time.time())

            new_event, sync_state, new_event_time = self.__get_gnss_status(
                holdover_time, freq, sync_state, last_event_time, gnss)
            LOG.info("%s gnss_status: state is %s, new_event is %s"
                     % (gnss.ts2phc_service_name, sync_state, new_event))

            if new_event or forced:
                # update context
                self.gnsstracker_context_lock.acquire()
                self.gnsstracker_context[
                    gnss.ts2phc_service_name]['sync_state'] = sync_state
                self.gnsstracker_context[gnss.ts2phc_service_name][
                    'last_event_time'] = new_event_time
                self.gnsstracker_context_lock.release()

                LOG.debug("Publish GNSS status.")

                # publish new event in API version v2 format
                resource_address = utils.format_resource_address(
                    self.node_name, 
                    constants.SOURCE_SYNC_GNSS_SYNC_STATUS, 
                    gnss.ts2phc_service_name)
                lastStatus[gnss.ts2phc_service_name] = {
                    'id': uuidutils.generate_uuid(),
                    'specversion': constants.SPEC_VERSION,
                    'source': constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                    'type': source_type[
                        constants.SOURCE_SYNC_GNSS_SYNC_STATUS],
                    'time': new_event_time,
                    'data': {
                        'version': constants.DATA_VERSION,
                        'values': [
                            {
                                'data_type': constants.DATA_TYPE_NOTIFICATION,
                                'ResourceAddress': resource_address,
                                'value_type': constants.VALUE_TYPE_ENUMERATION,
                                'value': sync_state.upper()
                            }
                        ]
                    }
                }
                newStatus.append(lastStatus[gnss.ts2phc_service_name])
                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_GNSS_SYNC_STATUS)
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_ALL)
                else:
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_GNSS_SYNC_STATUS)
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_ALL)                  

    def __publish_ptpstatus(self, forced=False):

        for ptp_monitor in self.ptp_monitor_list:
            # Ensure that status structs are cleared between each iteration
            newStatus = []
            newClockClassStatus = []
            lastStatus = {}
            lastClockClassStatus = {}

            holdover_time = float(self.ptptracker_context[
                ptp_monitor.ptp4l_service_name]['holdover_seconds'])
            freq = float(self.ptptracker_context[
                ptp_monitor.ptp4l_service_name]['poll_freq_seconds'])
            sync_state = \
                self.ptptracker_context[ptp_monitor.ptp4l_service_name].get(
                    'sync_state', 'Unknown')
            last_event_time = \
                self.ptptracker_context[ptp_monitor.ptp4l_service_name].get(
                    'last_event_time', time.time())

            new_event, sync_state, new_event_time = self.__get_ptp_status(
                holdover_time, freq, sync_state, last_event_time, ptp_monitor)
            LOG.info("%s PTP sync state: state is %s, new_event is %s" % (
                ptp_monitor.ptp4l_service_name, sync_state, new_event))

            new_clock_class_event, clock_class, clock_class_event_time = \
                ptp_monitor.get_ptp_clock_class()
            LOG.info("%s PTP clock class: clockClass is %s, new_event is %s"
                     % (ptp_monitor.ptp4l_service_name, clock_class,
                        new_clock_class_event))
            if new_event or forced:
                # update context
                self.ptptracker_context_lock.acquire()
                self.ptptracker_context[ptp_monitor.ptp4l_service_name][
                    'sync_state'] = sync_state
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
                    self.node_name, 
                    constants.SOURCE_SYNC_PTP_LOCK_STATE, 
                    ptp_monitor.ptp4l_service_name)
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
                                'value': sync_state.upper()
                            }
                        ]
                    }
                }
                self.ptptracker_context_lock.release()
                newStatus.append(lastStatus[ptp_monitor.ptp4l_service_name])

                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_PTP_LOCK_STATE)
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_ALL)
                else:
                    self.ptpeventproducer.publish_status(
                        lastStatus, constants.SOURCE_SYNC_PTP_LOCK_STATE)
                    self.ptpeventproducer.publish_status(
                        lastStatus, constants.SOURCE_SYNC_ALL)

            if new_clock_class_event or forced:
                # update context
                self.ptptracker_context_lock.acquire()
                self.ptptracker_context[ptp_monitor.ptp4l_service_name][
                    'clock_class'] = clock_class
                self.ptptracker_context[ptp_monitor.ptp4l_service_name][
                    'last_clock_class_event_time'] \
                    = clock_class_event_time

                resource_address = utils.format_resource_address(
                    self.node_name, 
                    constants.SOURCE_SYNC_PTP_CLOCK_CLASS, 
                    ptp_monitor.ptp4l_service_name)

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
                newClockClassStatus.append(lastClockClassStatus[ptp_monitor.ptp4l_service_name])
                self.ptptracker_context_lock.release()
                LOG.info("Publishing clockClass for %s: %s"
                         % (ptp_monitor.ptp4l_service_name, clock_class))

                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newClockClassStatus,
                        constants.SOURCE_SYNC_PTP_CLOCK_CLASS)
                    self.ptpeventproducer.publish_status(newClockClassStatus,
                                                        constants.SOURCE_SYNC_ALL)
                else:
                    self.ptpeventproducer.publish_status(
                        lastClockClassStatus,
                        constants.SOURCE_SYNC_PTP_CLOCK_CLASS)
                    self.ptpeventproducer.publish_status(lastClockClassStatus,
                                                        constants.SOURCE_SYNC_ALL)


class DaemonControl(object):

    def __init__(self, sqlalchemy_conf_json, daemon_context_json,
                 process_worker=None):
        self.event = mp.Event()
        self.daemon_context = json.loads(daemon_context_json)
        self.node_name = self.daemon_context['THIS_NODE_NAME']
        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.sqlalchemy_conf_json = sqlalchemy_conf_json
        self.daemon_context_json = daemon_context_json
        self.process_worker = process_worker

    def refresh(self):
        self.process_worker(self.event, self.sqlalchemy_conf_json,
                            self.daemon_context_json)
        self.event.set()
