#
# Copyright (c) 2022-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import os
import re

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class CguHandler:
    def __init__(self, config_file, nmea_serialport=None, pci_addr=None, 
                 cgu_path=None):
        self.config_file = config_file
        self.nmea_serialport = nmea_serialport
        self.pci_addr = pci_addr
        self.cgu_path = cgu_path
        self.cgu_output_raw = ""
        self.cgu_output_parsed = {}

    def get_gnss_nmea_serialport_from_ts2phc_config(self):
        # Read a tstphc config file and return the ts2phc.nmea_serialport
        nmea_serialport = None
        try:
            with open(self.config_file, 'r') as infile:
                for line in infile:
                    if constants.NMEA_SERIALPORT in line:
                        nmea_serialport = line.split(' ')[1].strip('\n')
                        break
            self.nmea_serialport = nmea_serialport
            return
        except (FileNotFoundError, PermissionError) as err:
            LOG.error(err)
            raise

    def convert_nmea_serialport_to_pci_addr(self):
        # Parse the nmea_serialport value into a PCI address so that we can
        # later find the cgu
        # Returns the address or None
        pci_addr = None
        # Remove the /dev portion of the path
        nmea_serialport = self.nmea_serialport.split('/')[2]
        LOG.debug("Looking for nmea_serialport value: %s" % nmea_serialport)
        # Buld uevent path
        uevent_file = '/sys/class/gnss/' + nmea_serialport + '/device/uevent'

        try:
            with open(uevent_file, 'r') as file:
                for line in file:
                    if 'PCI_SLOT_NAME' in line:
                        # Get the portion after the '=' sign
                        pci_addr = re.split('=', line)[1].strip('\n')
                        LOG.debug("Found with PCI addr: %s" % pci_addr)
                        break
        except (FileNotFoundError, PermissionError) as err:
            LOG.error(err)

        self.pci_addr = pci_addr

    def get_cgu_path_from_pci_addr(self):
        # Search for a cgu file using the given pci address
        cgu_path = "/ice/" + self.pci_addr + "/cgu"
        if os.path.exists(cgu_path):
            LOG.debug("PCI address %s has cgu path %s" %
                      (self.pci_addr, cgu_path))
            self.cgu_path = cgu_path
            return
        else:
            LOG.error("Could not find cgu path for PCI address %s" %
                      self.pci_addr)
            raise FileNotFoundError

    def read_cgu(self):
        # Read a given cgu path and return the output in a parseable structure
        cgu_output = None
        if os.path.exists(self.cgu_path):
            with open(self.cgu_path, 'r') as infile:
                cgu_output = infile.read()
        self.cgu_output_raw = cgu_output

    def cgu_output_to_dict(self):
        # Take raw cgu output and parse it into a dict
        cgu_output = self.cgu_output_raw.splitlines()
        cgu_dict = {'input': {},
                    'EEC DPLL': {
                        'Current reference': '',
                        'Status': ''
                    },
                    'PPS DPLL': {
                        'Current reference': '',
                        'Status': '',
                        'Phase offset': ''
                    }
                    }
        # Get the input state table start and end lines
        # Can vary in length depending on NIC types
        for index, line in enumerate(cgu_output):
            if "input (idx)" in line:
                table_start = index + 2
            if "EEC DPLL:" in line:
                dpll_start = index
                table_end = index - 1

        for line in cgu_output[table_start:table_end]:
            # Build a dict out of the table
            dict_to_insert = {
                re.split(' +', line)[1]: {
                    'state': re.split(' +', line)[4],
                    'priority': {
                        'EEC': re.split(' +', line)[6],
                        'PPS': re.split(' +', line)[8]
                    }
                }
            }
            cgu_dict['input'].update(dict_to_insert)

        # Add the DPLL data below the table
        # Set the line offsets for each item we want
        eec_current_ref = dpll_start + 1
        eec_status = dpll_start + 2
        pps_current_ref = dpll_start + 5
        pps_status = dpll_start + 6
        pps_phase_offset = dpll_start + 7

        cgu_dict['EEC DPLL']['Current reference'] = \
            re.split('[ \t]+', cgu_output[eec_current_ref])[-1]
        cgu_dict['EEC DPLL']['Status'] = re.split('[ \t]+', cgu_output[eec_status])[-1]
        cgu_dict['PPS DPLL']['Current reference'] = \
            re.split('[ \t]+', cgu_output[pps_current_ref])[-1]
        cgu_dict['PPS DPLL']['Status'] = re.split('[ \t]+', cgu_output[pps_status])[-1]
        cgu_dict['PPS DPLL']['Phase offset'] = \
            re.split('[ \t]+', cgu_output[pps_phase_offset])[-1]

        self.cgu_output_parsed = cgu_dict
