#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
from abc import ABC, abstractmethod
from datetime import datetime

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers.cgu_handler import CguHandler

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
    event_time = None
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

        self.dmesg_values_to_check = {'pin': 'GNSS-1PPS', 'pci_addr': self.gnss_cgu_handler.pci_addr}

        # Initialize status
        if self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Current reference'] == 'GNSS-1PPS':
            self.gnss_eec_state = self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Status']

        if self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Current reference'] == 'GNSS-1PPS':
            self.gnss_pps_state = self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Status']

        self.event_time = datetime.now().timestamp()

    def update(self, subject, matched_line) -> None:
        LOG.info("Kernel event detected. %s" % matched_line)
        LOG.debug("GnssMonitor handler logic would run now")
        self.set_gnss_status()

    def set_gnss_status(self):
        self.event_time = datetime.now().timestamp()
        self.gnss_cgu_handler.read_cgu()
        self.gnss_cgu_handler.cgu_output_to_dict()
        self.gnss_eec_state = self.gnss_cgu_handler.cgu_output_parsed['EEC DPLL']['Status']
        self.gnss_pps_state = self.gnss_cgu_handler.cgu_output_parsed['PPS DPLL']['Status']
        LOG.debug("GNSS EEC Status is: %s" % self.gnss_eec_state)
        LOG.debug("GNSS PPS Status is: %s" % self.gnss_pps_state)

    def __publish_gnss_status(self, force=False):
        LOG.debug("Publish GNSS status.")
        # TODO implement a publisher class to handle this
        pass
