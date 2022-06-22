#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import os
import re
import sys

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class CguHandler:
    def __init__(self, config_file, nmea_serialport=None, pci_addr=None, cgu_path=None):
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

    def convert_nmea_serialport_to_pci_addr(self, dmesg_path="/logs/dmesg"):
        # Parse the nmea_serialport value into a PCI address so that we can later find the cgu
        # Returns the address or None
        pci_addr = None
        # Get only the ttyGNSS_1800_0 portion of the path
        nmea_serialport = self.nmea_serialport.split('/')[2]
        LOG.debug("Looking for nmea_serialport value: %s" % nmea_serialport)

        with open(dmesg_path, 'r') as dmesg:
            for line in dmesg:
                if nmea_serialport in line:
                    # Regex split to make any number of spaces the delimiter
                    # Eg. [    4.834255] ice 0000:18:00.0: ttyGNSS_1800_0 registered
                    # Becomes: 0000:18:00.0
                    pci_addr = re.split(' +', line)[3].strip(':')
        self.pci_addr = pci_addr
        return

    def get_cgu_path_from_pci_addr(self):
        # Search for a cgu file using the given pci address
        cgu_path = "/ice/" + self.pci_addr + "/cgu"
        if os.path.exists(cgu_path):
            LOG.debug("PCI address %s has cgu path %s" % (self.pci_addr, cgu_path))
            self.cgu_path = cgu_path
            return
        else:
            LOG.error("Could not find cgu path for PCI address %s" % self.pci_addr)
            raise FileNotFoundError

    def read_cgu(self):
        # Read a given cgu path and return the output in a parseable structure
        cgu_output = None
        if os.path.exists(self.cgu_path):
            with open(self.cgu_path, 'r') as infile:
                cgu_output = infile.read()
        self.cgu_output_raw = cgu_output
        return

    def cgu_output_to_dict(self):
        # Take raw cgu output and parse it into a dict
        cgu_output = self.cgu_output_raw.splitlines()
        LOG.debug("CGU output: %s" % cgu_output)
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

        for line in cgu_output[7:14]:
            # Build a dict out of the 7 line table
            dict_to_insert = {re.split(' +', line)[1]: {'state': re.split(' +', line)[4],
                                                        'priority': {'EEC': re.split(' +', line)[6],
                                                                     'PPS': re.split(' +', line)[8]}
                                                        }
                              }
            cgu_dict['input'].update(dict_to_insert)

        # Add the DPLL data below the table
        cgu_dict['EEC DPLL']['Current reference'] = re.split('[ \t]+', cgu_output[16])[3]
        cgu_dict['EEC DPLL']['Status'] = re.split('[ \t]+', cgu_output[17])[2]
        cgu_dict['PPS DPLL']['Current reference'] = re.split('[ \t]+', cgu_output[20])[3]
        cgu_dict['PPS DPLL']['Status'] = re.split('[ \t]+', cgu_output[21])[2]
        cgu_dict['PPS DPLL']['Phase offset'] = re.split('[ \t]+', cgu_output[22])[3]

        self.cgu_output_parsed = cgu_dict
        return
