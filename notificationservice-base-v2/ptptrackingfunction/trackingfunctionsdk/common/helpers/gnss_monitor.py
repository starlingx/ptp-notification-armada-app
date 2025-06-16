#
# Copyright (c) 2022-2025 Wind River Systems, Inc.
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
                 cgu_path=None):
        self.config_file = config_file
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

        self.set_ptp_devices()
        # Setup GNSS data
        self.gnss_cgu_handler = CguHandler(config_file, nmea_serialport,
                                           pci_addr, cgu_path)
        self.gnss_cgu_handler.read_cgu()

        # Initialize status
        if self.gnss_cgu_handler.get_eec_current_ref() == constants.GNSS_PIN \
              or self.gnss_cgu_handler.get_eec_pin_type() == constants.GNSS_TYPE:
            self.gnss_eec_state = self.gnss_cgu_handler.get_eec_status()

        if self.gnss_cgu_handler.get_pps_current_ref() == constants.GNSS_PIN \
              or self.gnss_cgu_handler.get_pps_pin_type() == constants.GNSS_TYPE:
            self.gnss_pps_state = self.gnss_cgu_handler.get_pps_status()

    def set_ptp_devices(self):
        ptp_devices = set()
        phc_interfaces = self._check_config_file_interfaces()
        for phc_interface in phc_interfaces:
            ptp_device = utils.get_interface_phc_device(phc_interface)
            if ptp_device is not None:
                ptp_devices.add(ptp_device)
        self.ptp_devices = list(ptp_devices)
        LOG.debug("TS2PHC PTP devices are %s" % self.ptp_devices)

    def get_ptp_devices(self):
        return self.ptp_devices

    def _check_config_file_interfaces(self):
        phc_interfaces = []
        with open(self.config_file, 'r') as f:
            config_lines = f.readlines()
            config_lines = [line.rstrip() for line in config_lines]

        for line in config_lines:
            # Find the interface value inside the square brackets
            if re.match(r"^\[.*\]$", line) and line != "[global]":
                phc_interface = line.strip("[]")
                LOG.debug("TS2PHC interface is %s" % phc_interface)
                phc_interfaces.append(phc_interface)

        return phc_interfaces

    def update(self, subject, matched_line) -> None:
        LOG.info("Kernel event detected. %s", matched_line)
        self.set_gnss_status()

    def set_gnss_status(self):
        """Set GNSS Status based on CGU information"""

        # Check that ts2phc is running, else Freerun
        if not os.path.\
            isfile(f'/var/run/ts2phc-{self.ts2phc_service_name}.pid'):
            LOG.warning("TS2PHC instance %s is not running, "
                        "reporting GNSS unlocked.", self.ts2phc_service_name)
            self._state = GnssState.Failure_Nofix
            return

        self.gnss_cgu_handler.read_cgu()

        self.gnss_eec_state = self.gnss_cgu_handler.get_eec_status()
        self.gnss_pps_state = self.gnss_cgu_handler.get_pps_status()
        LOG.debug("GNSS EEC Status is: %s", self.gnss_eec_state)
        LOG.debug("GNSS PPS Status is: %s", self.gnss_pps_state)
        if self.gnss_pps_state == constants.GNSS_LOCKED_HO_ACQ and \
           self.gnss_eec_state == constants.GNSS_LOCKED_HO_ACQ:
            self._state = GnssState.Synchronized
        else:
            self._state = GnssState.Failure_Nofix

        LOG.debug("Set state GNSS to %s", self._state)

    def get_gnss_status(self, sync_state, event_time):
        """Return GNSS status and determine if GNSS state has changed"""

        previous_sync_state = sync_state

        self.set_gnss_status()

        # determine if GNSS state has changed since the last check
        if self._state != previous_sync_state:
            new_event = True
            event_time = datetime.datetime.now(datetime.timezone.utc)\
                .timestamp()
        else:
            new_event = False
        return new_event, self._state, event_time
