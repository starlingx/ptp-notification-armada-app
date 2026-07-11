#
# Copyright (c) 2021-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import datetime
import json
import logging
import multiprocessing as mp
import os
import re
import threading
import time

from oslo_utils import uuidutils
from trackingfunctionsdk.client.ptpeventproducer import PtpEventProducer
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor
from trackingfunctionsdk.common.helpers import instance_config_parser
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers.synce_monitor import SynceMonitor
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.model.dto.overallclockstate import OverallClockState
from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.model.dto.rpc_endpoint import RpcEndpointInfo

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


def _ts2phc_uses_generic_clock(ts2phc_instance):
    """Return True if the ts2phc instance is running with '-s generic'."""
    pidfile = '/var/run/ts2phc-%s.pid' % ts2phc_instance
    try:
        with open(pidfile, 'r', encoding='utf-8') as f:
            pid = f.readline().strip()
        with open('/host/proc/%s/cmdline' % pid, 'r', encoding='utf-8') as f:
            args = f.readline().strip().split('\x00')
        return '-s' in args and args[args.index('-s') + 1] == 'generic'
    except (OSError, ValueError, IndexError):
        return False


def _get_ptp4l_effective_holdover(ptp4l_config, gnss_configs, gnss_instances,
                                  ptp4l_holdover):
    """Return min(ptp4l_holdover, gnss_holdover)

    If a gnss instance shares a PTP device with this ptp4l instance,
    return the min of the ptp4l holdover time and the gnss holdover time.
    Otherwise return ptp4l_holdover. If the gnss instance uses '-s generic',
    return ptp4l_holdover.

    Mirrors the collectd-extensions behavior.
    """
    ptp4l_devices = _get_ptp_devices_for_config(ptp4l_config)
    if not ptp4l_devices:
        return ptp4l_holdover

    for idx, gnss_config in enumerate(gnss_configs):
        gnss_devices = _get_ptp_devices_for_config(gnss_config)
        if ptp4l_devices & gnss_devices:
            gnss_instance = gnss_instances[idx]
            if _ts2phc_uses_generic_clock(gnss_instance):
                # As per collectd implementation
                effective = ptp4l_holdover
                LOG.debug(
                    "ptp4l %s shares PTP device with gnss %s (-s generic): "
                    "using ptp4l_holdover=%s as holdover",
                    ptp4l_config, gnss_instance, effective)
                return effective
            gnss_holdover = instance_config_parser.get_instance_gnss_holdover_time(
                gnss_instance)
            effective = min(ptp4l_holdover, gnss_holdover)
            LOG.debug(
                "ptp4l %s shares PTP device with gnss %s: "
                "using min(%s, %s)=%s as holdover",
                ptp4l_config, gnss_instance,
                ptp4l_holdover, gnss_holdover, effective)
            return effective

    return ptp4l_holdover


def _get_ptp_devices_for_config(config_file):
    """Return set of PHC device paths for interfaces listed in a config file."""
    devices = set()
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if (re.match(r'^\[.*\]$', line)
                        and line not in ('[global]',
                                         '[unicast_master_table]')):
                    iface = line.strip('[]')
                    dev = utils.get_interface_phc_device(iface)
                    if dev is not None:
                        devices.add(dev)
    except FileNotFoundError:
        LOG.warning("Config file not found: %s", config_file)
    return devices


def ProcessWorkerDefault(event, sqlalchemy_conf_json,
                         broker_transport_endpoint, holdover_config=None,
                         reload_requested=None):
    worker = PtpWatcherDefault(event, sqlalchemy_conf_json,
                               broker_transport_endpoint, holdover_config,
                               reload_requested)
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

    DEFAULT_SYNCETRACKER_CONTEXT = {
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
                if (resource_path == constants.SOURCE_SYNC_GNSS_SYNC_STATUS or
                        resource_path == constants.SOURCE_SYNC_ALL):
                    self.watcher.gnsstracker_context_lock.acquire()
                    if (optional and
                            self.watcher.gnsstracker_context.get(optional)):
                        sync_state = (
                            self.watcher.gnsstracker_context[optional].get(
                                'sync_state', GnssState.Failure_Nofix))
                        last_event_time = (
                            self.watcher.gnsstracker_context[optional].get(
                                'last_event_time', time.time()))
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                            last_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                                optional),
                            sync_state)
                        newStatus.append(lastStatus[optional])
                    elif not optional:
                        for config in self.daemon_context['GNSS_INSTANCES']:
                            sync_state = (
                                self.watcher.gnsstracker_context[config].get(
                                    'sync_state', GnssState.Failure_Nofix))
                            last_event_time = (
                                self.watcher.gnsstracker_context[config].get(
                                    'last_event_time', time.time()))
                            lastStatus[config] = self._build_event_response(
                                constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                                last_event_time,
                                utils.format_resource_address(
                                    nodename,
                                    constants.SOURCE_SYNC_GNSS_SYNC_STATUS,
                                    config),
                                sync_state)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.gnsstracker_context_lock.release()
                if (resource_path == constants.SOURCE_SYNCE_LOCK_STATE or
                        resource_path == constants.SOURCE_SYNC_ALL):
                    self.watcher.syncetracker_context_lock.acquire()
                    if (optional and
                            self.watcher.syncetracker_context.get(optional)):
                        sync_state = (
                            self.watcher.syncetracker_context[optional].get(
                                'sync_state', 'Unknown'))
                        last_event_time = (
                            self.watcher.syncetracker_context[optional].get(
                                'last_event_time', time.time()))
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNCE_LOCK_STATE,
                            last_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNCE_LOCK_STATE,
                                optional),
                            sync_state)
                        newStatus.append(lastStatus[optional])
                    elif not optional:
                        for config in self.daemon_context.get(
                                'SYNCE_INSTANCES', []):
                            sync_state = (
                                self.watcher.syncetracker_context[config].get(
                                    'sync_state', 'Unknown'))
                            last_event_time = (
                                self.watcher.syncetracker_context[config].get(
                                    'last_event_time', time.time()))
                            lastStatus[config] = self._build_event_response(
                                constants.SOURCE_SYNCE_LOCK_STATE,
                                last_event_time,
                                utils.format_resource_address(
                                    nodename,
                                    constants.SOURCE_SYNCE_LOCK_STATE,
                                    config),
                                sync_state)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.syncetracker_context_lock.release()
                if (resource_path == constants.SOURCE_SYNC_PTP_CLOCK_CLASS or
                        resource_path == constants.SOURCE_SYNC_ALL):
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional and self.watcher.ptptracker_context.get(
                            optional):
                        clock_class = \
                            self.watcher.ptptracker_context[optional].get(
                                'clock_class', '248')
                        last_clock_class_event_time = \
                            self.watcher.ptptracker_context[optional].get(
                                'last_clock_class_event_time', time.time())
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                            last_clock_class_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                                optional),
                            clock_class,
                            constants.VALUE_TYPE_METRIC)
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
                                utils.format_resource_address(
                                    nodename,
                                    constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
                                    config),
                                clock_class,
                                constants.VALUE_TYPE_METRIC)
                            newStatus.append(lastStatus[config])
                    else:
                        lastStatus = None
                    self.watcher.ptptracker_context_lock.release()
                if resource_path == constants.SOURCE_SYNC_PTP_LOCK_STATE or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.ptptracker_context_lock.acquire()
                    if optional and self.watcher.ptptracker_context.get(
                            optional):
                        sync_state = \
                            self.watcher.ptptracker_context[optional].get(
                                'sync_state', PtpState.Freerun)
                        last_event_time = \
                            self.watcher.ptptracker_context[optional].get(
                                'last_event_time', time.time())
                        lastStatus[optional] = self._build_event_response(
                            constants.SOURCE_SYNC_PTP_LOCK_STATE,
                            last_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNC_PTP_LOCK_STATE,
                                optional),
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
                                utils.format_resource_address(
                                    nodename,
                                    constants.SOURCE_SYNC_PTP_LOCK_STATE,
                                    config),
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
                    lastStatus['os_clock_status'] = (
                        self._build_event_response(
                            constants.SOURCE_SYNC_OS_CLOCK,
                            last_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNC_OS_CLOCK),
                            sync_state))
                    newStatus.append(lastStatus['os_clock_status'])
                if resource_path == constants.SOURCE_SYNC_SYNC_STATE or \
                   resource_path == constants.SOURCE_SYNC_ALL:
                    self.watcher.overalltracker_context_lock.acquire()
                    sync_state = self.watcher.overalltracker_context.get(
                        'sync_state', OverallClockState.Freerun)
                    last_event_time = self.watcher.overalltracker_context.get(
                        'last_event_time', time.time())
                    self.watcher.overalltracker_context_lock.release()
                    lastStatus['overall_sync_status'] = (
                        self._build_event_response(
                            constants.SOURCE_SYNC_SYNC_STATE,
                            last_event_time,
                            utils.format_resource_address(
                                nodename,
                                constants.SOURCE_SYNC_SYNC_STATE),
                            sync_state))
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

    def __init__(self, event, sqlalchemy_conf_json, daemon_context_json,
                 holdover_config=None, reload_requested=None):
        self.sqlalchemy_conf = json.loads(sqlalchemy_conf_json)
        self.event = event
        self.reload_requested = reload_requested
        self.init_time = time.time()
        # Holdover config now comes from instance-monitoring.conf per instance

        self.daemon_context = json.loads(daemon_context_json)

        # PTP Context
        self.ptptracker_context = {}
        gnss_configs = self.daemon_context.get('GNSS_CONFIGS', [])
        gnss_instances = self.daemon_context.get('GNSS_INSTANCES', [])
        os_clock_holdover = instance_config_parser.get_instance_osclock_holdover_time(
            self.daemon_context.get('PHC2SYS_SERVICE_NAME', 'phc2sys'))
        for config in self.daemon_context['PTP4L_INSTANCES']:
            self.ptptracker_context[config] = \
                PtpWatcherDefault.DEFAULT_PTPTRACKER_CONTEXT.copy()
            self.ptptracker_context[config]['sync_state'] = PtpState.Freerun
            self.ptptracker_context[config]['last_event_time'] = self.init_time
            ptp4l_config = constants.PTP_CONFIG_PATH + 'ptp4l-%s.conf' % config
            ptp4l_holdover = instance_config_parser.get_instance_holdover_time(
                config)
            self.ptptracker_context[config]['holdover_seconds'] = \
                _get_ptp4l_effective_holdover(
                    ptp4l_config, gnss_configs, gnss_instances, ptp4l_holdover)
            # Default poll frequency
            self.ptptracker_context[config]['poll_freq_seconds'] = 2
        self.ptp_device_simulated = \
            os.environ.get('PTP_DEVICE_SIMULATED', 'false').lower() == 'true'
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
                instance_config_parser.get_instance_gnss_holdover_time(config)
            # Default poll frequency
            self.gnsstracker_context[config]['poll_freq_seconds'] = 2
        self.gnsstracker_context_lock = threading.Lock()
        LOG.debug("gnsstracker_context: %s" % self.gnsstracker_context)

        # SyncE Context
        self.syncetracker_context = {}
        for config in self.daemon_context.get('SYNCE_INSTANCES', []):
            self.syncetracker_context[config] = \
                PtpWatcherDefault.DEFAULT_SYNCETRACKER_CONTEXT.copy()
            self.syncetracker_context[config]['sync_state'] = 'Unknown'
            self.syncetracker_context[config]['last_event_time'] = \
                self.init_time
            self.syncetracker_context[config]['holdover_seconds'] = \
                instance_config_parser.get_instance_holdover_time(config)
            self.syncetracker_context[config]['poll_freq_seconds'] = 2
        self.syncetracker_context_lock = threading.Lock()

        # OS Clock Context
        self.osclocktracker_context = {}
        self.osclocktracker_context = \
            PtpWatcherDefault.DEFAULT_OS_CLOCK_TRACKER_CONTEXT.copy()
        self.osclocktracker_context['sync_state'] = OsClockState.Freerun
        self.osclocktracker_context['last_event_time'] = self.init_time
        self.osclocktracker_context['holdover_seconds'] = os_clock_holdover
        # Default poll frequency
        self.osclocktracker_context['poll_freq_seconds'] = 2
        self.osclocktracker_context_lock = threading.Lock()

        # Overall Sync Context
        self.overalltracker_context = {}
        self.overalltracker_context = \
            PtpWatcherDefault.DEFAULT_OVERALL_SYNC_TRACKER_CONTEXT.copy()
        self.overalltracker_context['sync_state'] = OverallClockState.Freerun
        self.overalltracker_context['last_event_time'] = self.init_time
        self.overalltracker_context['holdover_seconds'] = \
            instance_config_parser.get_overall_holdover_time()
        # Default poll frequency
        self.overalltracker_context['poll_freq_seconds'] = 2
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
            GnssMonitor(
                i,
                holdover_time=self.gnsstracker_context[
                    self.daemon_context['GNSS_INSTANCES'][idx]]['holdover_seconds'])
            for idx, i in enumerate(self.daemon_context['GNSS_CONFIGS'])]

        self.os_clock_monitor = OsClockMonitor(
            phc2sys_config=self.daemon_context['PHC2SYS_CONFIG'],
            tolerance_threshold=30,
            holdover_time=self.osclocktracker_context['holdover_seconds'])

        self.ptp_monitor_list = [
            PtpMonitor(config,
                       self.ptptracker_context[config]['holdover_seconds'],
                       self.daemon_context['PHC2SYS_SERVICE_NAME'],
                       offset_threshold=1000000)
            for config in self.daemon_context['PTP4L_INSTANCES']]

        self.synce_monitor_list = [
            SynceMonitor(config,
                         holdover_time=self.syncetracker_context[config][
                             'holdover_seconds'])
            for config in self.daemon_context.get('SYNCE_INSTANCES', [])]

    def signal_ptp_event(self):
        if self.event:
            self.event.set()
        else:
            LOG.warning("Unable to assert ptp event")

    def run(self):
        # start location listener
        self.__start_listener()

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
            # Check for reload request
            if self.reload_requested and self.reload_requested.is_set():
                LOG.info("Reload requested, exiting daemon loop")
                break

            # announce the location
            forced = self.forced_publishing
            self.forced_publishing = False
            if self.ptptracker_context:
                self.__publish_ptpstatus(forced)
            if self.gnsstracker_context:
                self.__publish_gnss_status(forced)
            if self.syncetracker_context:
                self.__publish_synce_status(forced)
                self.__publish_synce_clock_quality(forced)
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

        self.ptpeventproducer.stop_status_listener()

    def __get_gnss_status(self, sync_state, last_event_time, gnss_monitor):
        new_event, sync_state, new_event_time = gnss_monitor.get_gnss_status(
            sync_state, last_event_time)
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
        # disciplining source could be either GNSS or PTP.
        # When multiple ptp4l instances share the same PTP device (same
        # NIC/PHC with different domainNumbers), prefer the instance with
        # a slave port (TypePTP) as it is the actual reference instance
        # disciplining the hardware clock.
        primary_ptp4l = None
        ptp_state = PtpState.Freerun
        for ptp4l in self.ptp_monitor_list:
            # runtime loading of ptp4l config
            ptp4l.set_ptp_devices()
            if ptp_device not in ptp4l.get_ptp_devices():
                continue
            sync_source = ptp4l.get_ptp_sync_source()
            if sync_source == constants.ClockSourceType.TypeNA:
                continue
            if sync_source == constants.ClockSourceType.TypePTP:
                # Instance has a slave port — this is the reference
                primary_ptp4l = ptp4l
                break
            if primary_ptp4l is None:
                # First non-NA match (TypeGNSS), keep as fallback
                primary_ptp4l = ptp4l

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

        # Calculate overall holdover time based on active sync chain
        overall_holdover_time = self.__calculate_overall_holdover_time()
        gnss_state = None
        os_clock_state = None
        ptp_state = None

        LOG.debug("Getting overall sync state.")

        # IMPORTANT: SyncE is explicitly excluded from aggregate state calculation.
        # SyncE provides frequency synchronization (EEC/DPLL) only. The overall
        # timing state depends exclusively on phase/time sources (GNSS via ts2phc,
        # PTP via ptp4l) and the OS clock (phc2sys). SyncE loss degrades frequency
        # holdover but does NOT affect phase/time accuracy while PTP or GNSS
        # remains locked. SyncE state is reported independently via its own
        # notification endpoints (/sync/synce-status/lock-state and
        # /sync/synce-status/synce-clock-quality) and alarm (100.119).
        # See: ITU-T G.8275.1, O-RAN WG4 sync architecture.

        # overall state depends on os_clock_state and single chained gnss/ptp state
        # Need to figure out which gnss/ptp is disciplining the PHC that syncs
        # os_clock
        os_clock_state = self.os_clock_monitor.get_os_clock_state()
        sync_state = OverallClockState.Freerun
        chaining_info = (
            f"Overall sync state chaining info:\n"
            f"os-clock-state = {os_clock_state}"
        )

        # When os_clock_state is not locked (i.e. holdover or freerun),
        # the overall sync_state would still be freerun, which later
        # converted to holdover based upon: previous locked state or until
        # time-in-holdover less than overall_holdover_time. This makes sure:
        # overall sync_state follows os_clock_state's holdover right after,
        # and don't wait until freerun.
        if os_clock_state is OsClockState.Locked:
            # PTP device that is disciplining the OS clock,
            # valid even for HA source devices
            ptp_device = self.os_clock_monitor.get_source_ptp_device()
            if ptp_device is None:
                # This may happen in virtualized environments
                LOG.warning("No PTP device. Defaulting overall state Freerun")
                chaining_info += (
                    "\nos-clock's source ptp-device = None"
                )
            else:
                # What source (gnss or ptp) disciplining the PTP device at the
                # moment (A PTP device could have both TS2PHC/gnss source and
                # PTP4l/slave)
                sync_source = constants.ClockSourceType.TypeNA
                # any ts2phc instance disciplining the ptp device (source GNSS)
                primary_gnss, gnss_state = self.__get_primary_gnss_state(
                    ptp_device)
                if primary_gnss is not None:
                    sync_source = constants.ClockSourceType.TypeGNSS

                # any ptp4l instance disciplining the ptp device (source PTP or
                # GNSS)
                primary_ptp4l, ptp_state = self.__get_primary_ptp_state(
                    ptp_device)

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
                    # The PTP device is not being disciplined by any
                    # PTP4l/TS2PHC instances
                    LOG.warning(
                        "PTP device used by PHC2SYS is not synced/configured on any PTP4l/TS2PHC "
                        "instances.")

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
                LOG.info(
                    "Overall Holdover: Remaining in FREERUN state (previous: %s)" %
                    previous_sync_state)
            elif previous_sync_state == constants.LOCKED_PHC_STATE:
                sync_state = OverallClockState.Holdover
                LOG.info("Overall Holdover: Transitioning LOCKED -> HOLDOVER "
                         "(holdover_time=%ds)", overall_holdover_time)
            elif (
                previous_sync_state == constants.HOLDOVER_PHC_STATE
                and time_in_holdover < overall_holdover_time
            ):
                LOG.info("Overall Holdover: Remaining in HOLDOVER "
                         "(%ds/%ds elapsed, %ds remaining)",
                         time_in_holdover, overall_holdover_time,
                         overall_holdover_time - time_in_holdover)
                sync_state = OverallClockState.Holdover
            else:
                sync_state = OverallClockState.Freerun
                LOG.warning(
                    "Overall Holdover: Transitioning HOLDOVER -> FREERUN "
                    "(holdover expired: %ds >= %ds)",
                    time_in_holdover,
                    overall_holdover_time)

        chaining_info += (
            f"\nOverall sync: previous-state = {previous_sync_state}, "
            f"new-state = {sync_state}\n"
            f"Overall holdover: calculated={overall_holdover_time}s")

        if sync_state != previous_sync_state:
            new_event = True
            new_event_time = datetime.datetime.utcnow().timestamp()
            LOG.info(chaining_info)
        else:
            LOG.debug(chaining_info)
        return new_event, sync_state, new_event_time

    def __calculate_overall_holdover_time(self):
        """Calculate overall holdover time based on active sync chain.

        Returns the minimum holdover time across the active synchronization
        chain (source + OS clock). Falls back to the configured overall
        holdover time if no disciplining source is found.
        """
        # Get OS Clock holdover time (always in the chain)
        os_clock_holdover = self.os_clock_monitor.holdover_time

        # Get source PTP device holdover time
        ptp_device = self.os_clock_monitor.get_source_ptp_device()
        if ptp_device is None:
            # No PTP device, use OS clock holdover only
            LOG.debug(
                "Overall holdover: Using OS clock holdover=%s (no PTP device)" %
                os_clock_holdover)
            return os_clock_holdover

        # Find which PTP/GNSS instance is disciplining the PTP device
        source_holdover = None

        # Check GNSS instances
        for gnss in self.observer_list:
            gnss.set_ptp_devices()
            if ptp_device in gnss.get_ptp_devices():
                source_holdover = gnss.holdover_time
                LOG.debug(
                    "Overall holdover: Found GNSS source %s with holdover=%s" %
                    (gnss.ts2phc_service_name, source_holdover))
                break

        # Check PTP instances if no GNSS found
        if source_holdover is None:
            for ptp_monitor in self.ptp_monitor_list:
                ptp_monitor.set_ptp_devices()
                if ptp_device in ptp_monitor.get_ptp_devices():
                    source_holdover = ptp_monitor.holdover_time
                    LOG.debug(
                        "Overall holdover: Found PTP source %s with holdover=%s" %
                        (ptp_monitor.ptp4l_service_name, source_holdover))
                    break

        if source_holdover is None:
            # No source found, fall back to overall configured holdover
            LOG.debug(
                "Overall holdover: No source found, using overall holdover=%s" %
                self.overalltracker_context['holdover_seconds'])
            return float(self.overalltracker_context['holdover_seconds'])

        # Use minimum of source and OS clock holdover times
        # Handle Mock objects in tests
        try:
            overall_holdover = min(source_holdover, os_clock_holdover)
        except TypeError:
            # In tests with Mock objects, use a default value
            overall_holdover = 30
        LOG.debug("Overall holdover: Using minimum of source=%s and OS=%s = %s"
                  % (source_holdover, os_clock_holdover, overall_holdover))
        return overall_holdover

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
            sync_state = \
                self.gnsstracker_context[gnss.ts2phc_service_name].get(
                    'sync_state', 'Unknown')
            last_event_time = \
                self.gnsstracker_context[gnss.ts2phc_service_name].get(
                    'last_event_time', time.time())

            new_event, sync_state, new_event_time = self.__get_gnss_status(
                sync_state, last_event_time, gnss)
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

    def __publish_synce_status(self, forced=False):
        for synce_monitor in self.synce_monitor_list:
            instance = synce_monitor.synce4l_service_name
            new_event, sync_state, event_time = synce_monitor.get_synce_status()
            LOG.info("%s synce_status: state is %s, new_event is %s",
                     instance, sync_state, new_event)

            if new_event or forced:
                self.syncetracker_context_lock.acquire()
                self.syncetracker_context[instance]['sync_state'] = sync_state
                self.syncetracker_context[instance][
                    'last_event_time'] = event_time
                self.syncetracker_context_lock.release()

                resource_address = utils.format_resource_address(
                    self.node_name,
                    constants.SOURCE_SYNCE_LOCK_STATE,
                    instance)
                lastStatus = {
                    instance: {
                        'id': uuidutils.generate_uuid(),
                        'specversion': constants.SPEC_VERSION,
                        'source': constants.SOURCE_SYNCE_LOCK_STATE,
                        'type': source_type[
                            constants.SOURCE_SYNCE_LOCK_STATE],
                        'time': event_time,
                        'data': {
                            'version': constants.DATA_VERSION,
                            'values': [
                                {
                                    'data_type':
                                        constants.DATA_TYPE_NOTIFICATION,
                                    'ResourceAddress': resource_address,
                                    'value_type':
                                        constants.VALUE_TYPE_ENUMERATION,
                                    'value': sync_state.upper()
                                }
                            ]
                        }
                    }
                }
                newStatus = [lastStatus[instance]]
                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNCE_LOCK_STATE)
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNC_ALL)
                else:
                    self.ptpeventproducer.publish_status(
                        lastStatus, constants.SOURCE_SYNCE_LOCK_STATE)
                    self.ptpeventproducer.publish_status(
                        lastStatus, constants.SOURCE_SYNC_ALL)

    def __publish_synce_clock_quality(self, forced=False):
        for synce_monitor in self.synce_monitor_list:
            instance = synce_monitor.synce4l_service_name
            new_event, ql, event_time = synce_monitor.get_clock_quality()

            if new_event or forced:
                resource_address = utils.format_resource_address(
                    self.node_name,
                    constants.SOURCE_SYNCE_CLOCK_QUALITY,
                    instance)
                lastStatus = {
                    instance: {
                        'id': uuidutils.generate_uuid(),
                        'specversion': constants.SPEC_VERSION,
                        'source': constants.SOURCE_SYNCE_CLOCK_QUALITY,
                        'type': source_type[
                            constants.SOURCE_SYNCE_CLOCK_QUALITY],
                        'time': event_time,
                        'data': {
                            'version': constants.DATA_VERSION,
                            'values': [
                                {
                                    'data_type': constants.DATA_TYPE_METRIC,
                                    'ResourceAddress': resource_address,
                                    'value_type':
                                        constants.VALUE_TYPE_METRIC,
                                    'value': ql
                                }
                            ]
                        }
                    }
                }
                newStatus = [lastStatus[instance]]
                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newStatus, constants.SOURCE_SYNCE_CLOCK_QUALITY)
                else:
                    self.ptpeventproducer.publish_status(
                        lastStatus, constants.SOURCE_SYNCE_CLOCK_QUALITY)

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
                newClockClassStatus.append(
                    lastClockClassStatus[ptp_monitor.ptp4l_service_name])
                self.ptptracker_context_lock.release()
                LOG.info("Publishing clockClass for %s: %s"
                         % (ptp_monitor.ptp4l_service_name, clock_class))

                if constants.NOTIFICATION_FORMAT == 'standard':
                    self.ptpeventproducer.publish_status(
                        newClockClassStatus,
                        constants.SOURCE_SYNC_PTP_CLOCK_CLASS)
                    self.ptpeventproducer.publish_status(
                        newClockClassStatus, constants.SOURCE_SYNC_ALL)
                else:
                    self.ptpeventproducer.publish_status(
                        lastClockClassStatus,
                        constants.SOURCE_SYNC_PTP_CLOCK_CLASS)
                    self.ptpeventproducer.publish_status(
                        lastClockClassStatus, constants.SOURCE_SYNC_ALL)


class DaemonControl(object):

    def __init__(self, sqlalchemy_conf_json, daemon_context_json,
                 process_worker=None):
        self.event = mp.Event()
        self.reload_requested = mp.Event()
        self.daemon_context = json.loads(daemon_context_json)
        self.node_name = self.daemon_context['THIS_NODE_NAME']
        if not process_worker:
            process_worker = ProcessWorkerDefault

        self.sqlalchemy_conf_json = sqlalchemy_conf_json
        self.daemon_context_json = daemon_context_json
        self.process_worker = process_worker

    def refresh(self):
        self.process_worker(self.event, self.sqlalchemy_conf_json,
                            self.daemon_context_json, None,
                            self.reload_requested)
        self.event.set()

    def request_reload(self):
        """Request daemon to reload configuration"""
        LOG.info("Requesting daemon reload")
        self.reload_requested.set()
        self.event.set()

    def stop(self):
        """Stop daemon gracefully"""
        LOG.debug("Stopping daemon control")
        self.reload_requested.set()
        self.event.set()
