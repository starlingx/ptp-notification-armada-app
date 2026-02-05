#
# Copyright (c) 2022-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import datetime
import os.path
import re

from abc import ABC, abstractmethod

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers.cgu_handler import CguHandler
from trackingfunctionsdk.common.helpers.instance_config_parser import get_instance_holdover_time
from trackingfunctionsdk.model.dto.gnssstate import GnssState

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class Observer(ABC):
    @abstractmethod
    def update(self, subject, matched_line) -> None:
        """
        Receive update from subject.
        """
        pass


class GnssMonitor(Observer):
    gnss_eec_state = ""
    gnss_pps_state = ""
    _state = GnssState()
    gnss_cgu_handler = None

    def __init__(self, config_file, nmea_serialport=None, pci_addr=None,
                 cgu_path=None, holdover_time=30):
        self.config_file = config_file
        self.ts2phc_service_name = None
        try:
            pattern = '(?<=' + \
                      constants.TS2PHC_CONFIG_PATH + \
                      'ts2phc-).*(?=.conf)'
            match = re.search(pattern, self.config_file)
            self.ts2phc_service_name = match.group()
        except AttributeError:
            LOG.warning(
                "GnssMonitor: Unable to determine tsphc_service name from %s",
                self.config_file)

        self.holdover_time = get_instance_holdover_time(
            self.ts2phc_service_name, holdover_time)
        LOG.info("GNSS Monitor initialized: instance=%s, holdover_time=%ds",
                 self.ts2phc_service_name, self.holdover_time)

        self._sync_state = GnssState.Failure_Nofix
        self._event_time = datetime.datetime.utcnow().timestamp()

        self.set_ptp_devices()
        # Setup GNSS data
        self.gnss_cgu_handler = CguHandler(config_file, nmea_serialport,
                                           pci_addr, cgu_path)
        self.gnss_cgu_handler.read_cgu()

        # Initialize status
        eec_ref = self.gnss_cgu_handler.get_eec_current_ref()
        eec_type = self.gnss_cgu_handler.get_eec_pin_type()
        if eec_ref == constants.GNSS_PIN or eec_type == constants.GNSS_TYPE:
            self.gnss_eec_state = self.gnss_cgu_handler.get_eec_status()

        pps_ref = self.gnss_cgu_handler.get_pps_current_ref()
        pps_type = self.gnss_cgu_handler.get_pps_pin_type()
        if pps_ref == constants.GNSS_PIN or pps_type == constants.GNSS_TYPE:
            self.gnss_pps_state = self.gnss_cgu_handler.get_pps_status()

    def set_ptp_devices(self):
        ptp_devices = set()
        phc_interfaces = self._check_config_file_interfaces()
        for phc_interface in phc_interfaces:
            ptp_device = utils.get_interface_phc_device(phc_interface)
            if ptp_device is not None:
                ptp_devices.add(ptp_device)
        self.ptp_devices = list(ptp_devices)
        LOG.debug("TS2PHC PTP devices are %s", self.ptp_devices)

    def get_ptp_devices(self):
        return self.ptp_devices

    def _check_config_file_interfaces(self):
        phc_interfaces = []
        try:
            with open(self.config_file, 'r', encoding='utf-8') as config_file:
                config_lines = config_file.readlines()
                config_lines = [line.rstrip() for line in config_lines]
        except FileNotFoundError:
            LOG.warning("Config file not found: %s", self.config_file)
            return phc_interfaces

        for line in config_lines:
            # Find the interface value inside the square brackets
            if re.match(r"^\[.*\]$", line) and line != "[global]":
                phc_interface = line.strip("[]")
                LOG.debug("TS2PHC interface is %s", phc_interface)
                phc_interfaces.append(phc_interface)

        return phc_interfaces

    def update(self, subject, matched_line) -> None:
        LOG.info("Kernel event detected. %s", matched_line)
        self.set_gnss_status()

    def set_gnss_status(self):
        """Set GNSS Status based on CGU information"""

        # Check that ts2phc is running, else Freerun
        pid_file = f'/var/run/ts2phc-{self.ts2phc_service_name}.pid'
        if not os.path.isfile(pid_file):
            LOG.warning("TS2PHC instance %s is not running, "
                        "reporting GNSS unlocked.", self.ts2phc_service_name)
            self._state = GnssState.Failure_Nofix
            return

        self.gnss_cgu_handler.read_cgu()

        self.gnss_eec_state = self.gnss_cgu_handler.get_eec_status()
        self.gnss_pps_state = self.gnss_cgu_handler.get_pps_status()
        LOG.debug("GNSS EEC Status is: %s", self.gnss_eec_state)
        LOG.debug("GNSS PPS Status is: %s", self.gnss_pps_state)
        if (self.gnss_pps_state == constants.GNSS_LOCKED_HO_ACQ and
                self.gnss_eec_state == constants.GNSS_LOCKED_HO_ACQ):
            self._state = GnssState.Synchronized
        else:
            self._state = GnssState.Failure_Nofix

        LOG.debug("Set state GNSS to %s", self._state)

    def get_gnss_status(
            self,
            sync_state=None,
            event_time=None):
        """Return GNSS status and determine if GNSS state has changed

        Parameters are deprecated and maintained for backward compatibility.
        The method now manages state internally.
        """
        if sync_state is not None:
            self._sync_state = sync_state
        if event_time is not None:
            self._event_time = event_time

        previous_sync_state = self._sync_state
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = None
        if previous_sync_state == GnssState.Holdover:
            time_in_holdover = round(current_time - self._event_time)

        self.set_gnss_status()

        if self._state != GnssState.Synchronized:
            if previous_sync_state == GnssState.Synchronized:
                self._state = GnssState.Holdover
                LOG.info(
                    "GNSS Holdover: Transitioning SYNCHRONIZED -> HOLDOVER "
                    "(holdover_time=%ds)", self.holdover_time)
            elif (previous_sync_state == GnssState.Holdover and
                    time_in_holdover < self.holdover_time):
                LOG.info(
                    "GNSS Holdover: Remaining in HOLDOVER "
                    "(%ds/%ds elapsed, %ds remaining)",
                    time_in_holdover, self.holdover_time,
                    self.holdover_time - time_in_holdover)
                self._state = GnssState.Holdover
            else:
                self._state = GnssState.Failure_Nofix
                if previous_sync_state == GnssState.Holdover:
                    LOG.warning(
                        "GNSS Holdover: Transitioning HOLDOVER -> "
                        "FAILURE_NOFIX (holdover expired: %ds >= %ds)",
                        time_in_holdover, self.holdover_time)
                else:
                    LOG.info(
                        "GNSS Holdover: Remaining in FAILURE_NOFIX state "
                        "(previous: %s)", previous_sync_state)

        if self._state != previous_sync_state:
            new_event = True
            self._event_time = (datetime.datetime.now(datetime.timezone.utc)
                                .timestamp())
        else:
            new_event = False

        self._sync_state = self._state
        return new_event, self._state, self._event_time
