#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import datetime

from abc import ABC, abstractmethod

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import constants
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

    def __init__(self, config_file, nmea_serialport=None, pci_addr=None, cgu_path=None):
        self.config_file = config_file

        # Setup GNSS data
        self.gnss_cgu_handler = CguHandler(config_file, nmea_serialport, pci_addr, cgu_path)

        if self.gnss_cgu_handler.nmea_serialport is None:
            self.gnss_cgu_handler.get_gnss_nmea_serialport_from_ts2phc_config()
        if self.gnss_cgu_handler.pci_addr is None:
            self.gnss_cgu_handler.convert_nmea_serialport_to_pci_addr()
        if self.gnss_cgu_handler.cgu_path is None:
            self.gnss_cgu_handler.get_cgu_path_from_pci_addr()

        self.gnss_cgu_handler.read_cgu()
        self.gnss_cgu_handler.cgu_output_to_dict()

        self.dmesg_values_to_check = {'pin': 'GNSS-1PPS',
                                      'pci_addr': self.gnss_cgu_handler.pci_addr}

        # Initialize status
        if self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Current reference'] == 'GNSS-1PPS':
            self.gnss_eec_state = self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Status']

        if self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Current reference'] == 'GNSS-1PPS':
            self.gnss_pps_state = self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Status']

    def update(self, subject, matched_line) -> None:
        LOG.info("Kernel event detected. %s" % matched_line)
        LOG.debug("GnssMonitor handler logic would run now")
        self.set_gnss_status()

    def set_gnss_status(self):
        self.gnss_cgu_handler.read_cgu()
        self.gnss_cgu_handler.cgu_output_to_dict()
        self.gnss_eec_state = self.gnss_eec_state = \
            self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Status']
        self.gnss_pps_state = self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Status']
        LOG.debug("GNSS EEC Status is: %s" % self.gnss_eec_state)
        LOG.debug("GNSS PPS Status is: %s" % self.gnss_pps_state)
        if self.gnss_pps_state == 'locked_ho_ack' and self.gnss_eec_state == 'locked_ho_ack':
            self._state = GnssState.Locked
        else:
            self._state = GnssState.Freerun

        LOG.debug("Set state GNSS to %s" % self._state)

    def get_gnss_status(self, holdover_time, freq, sync_state, event_time):
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = round(current_time - event_time)
        previous_sync_state = sync_state
        max_holdover_time = (holdover_time - freq * 2)

        self.set_gnss_status()

        if self._state == constants.FREERUN_PHC_STATE:
            if previous_sync_state in [constants.UNKNOWN_PHC_STATE, constants.FREERUN_PHC_STATE]:
                self._state = constants.FREERUN_PHC_STATE
            elif previous_sync_state == constants.LOCKED_PHC_STATE:
                self._state = constants.HOLDOVER_PHC_STATE
            elif previous_sync_state == constants.HOLDOVER_PHC_STATE and \
                    time_in_holdover < max_holdover_time:
                self._state = constants.HOLDOVER_PHC_STATE
            else:
                self._state = constants.FREERUN_PHC_STATE

        # determine if os clock sync state has changed since the last check
        if self._state != previous_sync_state:
            new_event = True
            event_time = datetime.datetime.utcnow().timestamp()
        else:
            new_event = False
        return new_event, self._state, event_time

