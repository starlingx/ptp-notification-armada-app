#
# Copyright (c) 2022-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import unittest
import mock
from trackingfunctionsdk.common.helpers.cgu_handler import CguHandler
import os

testpath = os.environ.get("TESTPATH", "")

class CguHandlerTests(unittest.TestCase):
    testCguHandler = CguHandler(testpath + "test_input_files/ts2phc_valid.conf")
    missingCguHandler = CguHandler("./no_such_file.conf")
    invalidCguHandler = CguHandler(testpath + "test_input_files/ts2phc_invalid.conf")

    def test_get_gnss_nmea_serialport(self):
        # Test success path
        self.testCguHandler.get_gnss_nmea_serialport_from_ts2phc_config()
        self.assertEqual(self.testCguHandler.nmea_serialport, "/dev/ttyGNSS_1800_0")

        # Test missing / incorrect config file path
        with self.assertRaises(FileNotFoundError):
            self.missingCguHandler.get_gnss_nmea_serialport_from_ts2phc_config()

        # Test missing nmea_serialport in config
        self.invalidCguHandler.get_gnss_nmea_serialport_from_ts2phc_config()
        self.assertEqual(self.invalidCguHandler.nmea_serialport,
                         None)

    def test_convert_nmea_serialport_to_pci_addr(self):
        # Test success path
        self.testCguHandler.get_gnss_nmea_serialport_from_ts2phc_config()
        self.testCguHandler.convert_nmea_serialport_to_pci_addr(
            testpath + "test_input_files/mock_kern.log")
        self.assertEqual(self.testCguHandler.pci_addr, "0000:18:00.0")

        # Test pci address not found
        self.testCguHandler.nmea_serialport = "/dev/ttyGNSS_not_present"
        self.testCguHandler.convert_nmea_serialport_to_pci_addr(
            testpath + "test_input_files/mock_kern.log")
        self.assertEqual(self.testCguHandler.pci_addr, None)

    @mock.patch('trackingfunctionsdk.common.helpers.cgu_handler.os.path')
    def test_get_cgu_path_from_pci_addr(self, mock_path):
        # Setup mock
        mock_path.exists.return_value = True
        self.testCguHandler.get_gnss_nmea_serialport_from_ts2phc_config()
        self.testCguHandler.convert_nmea_serialport_to_pci_addr(
            testpath + "test_input_files/mock_kern.log")
        self.testCguHandler.get_cgu_path_from_pci_addr()
        self.assertEqual(self.testCguHandler.cgu_path, "/ice/0000:18:00.0/cgu")

        mock_path.exists.return_value = False
        with self.assertRaises(FileNotFoundError):
            self.testCguHandler.get_cgu_path_from_pci_addr()

    def test_cgu_output_to_dict_logan_beach(self):
        reference_dict = {
            "input": {
                "CVL-SDP22": {"state": "invalid", "priority": {"EEC": "8", "PPS": "8"}},
                "CVL-SDP20": {"state": "invalid", "priority": {"EEC": "15", "PPS": "3"}},
                "C827_0-RCLKA": {"state": "invalid", "priority": {"EEC": "4", "PPS": "4"}},
                "C827_0-RCLKB": {"state": "invalid", "priority": {"EEC": "5", "PPS": "5"}},
                "C827_1-RCLKA": {"state": "invalid", "priority": {"EEC": "6", "PPS": "6"}},
                "C827_1-RCLKB": {"state": "invalid", "priority": {"EEC": "7", "PPS": "7"}},
                "SMA1": {"state": "invalid", "priority": {"EEC": "1", "PPS": "1"}},
                "SMA2/U.FL2": {"state": "invalid", "priority": {"EEC": "2", "PPS": "2"}},
                "GNSS-1PPS": {"state": "valid", "priority": {"EEC": "0", "PPS": "0"}},
            },
            "EEC DPLL": {"Current reference": "GNSS-1PPS", "Status": "locked_ho_acq"},
            "PPS DPLL": {
                "Current reference": "GNSS-1PPS",
                "Status": "locked_ho_acq",
                "Phase offset": "-86",
            },
        }

        self.testCguHandler.cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        self.testCguHandler.read_cgu()
        self.testCguHandler.cgu_output_to_dict()
        self.assertDictEqual(self.testCguHandler.cgu_output_parsed, reference_dict)

    def test_cgu_output_to_dict_westport_channel(self):
        reference_dict = {
            "input": {
                "CVL-SDP22": {"state": "invalid", "priority": {"EEC": "8", "PPS": "8"}},
                "CVL-SDP20": {"state": "invalid", "priority": {"EEC": "15", "PPS": "3"}},
                "C827_0-RCLKA": {"state": "invalid", "priority": {"EEC": "4", "PPS": "4"}},
                "C827_0-RCLKB": {"state": "invalid", "priority": {"EEC": "5", "PPS": "5"}},
                "SMA1": {"state": "invalid", "priority": {"EEC": "1", "PPS": "1"}},
                "SMA2/U.FL2": {"state": "invalid", "priority": {"EEC": "2", "PPS": "2"}},
                "GNSS-1PPS": {"state": "valid", "priority": {"EEC": "0", "PPS": "0"}},
            },
            "EEC DPLL": {"Current reference": "GNSS-1PPS", "Status": "locked_ho_ack"},
            "PPS DPLL": {
                "Current reference": "GNSS-1PPS",
                "Status": "locked_ho_ack",
                "Phase offset": "295",
            },
        }
        self.testCguHandler.cgu_path = testpath + "test_input_files/mock_cgu_output_westport_channel"
        self.testCguHandler.read_cgu()
        self.testCguHandler.cgu_output_to_dict()
        self.assertDictEqual(self.testCguHandler.cgu_output_parsed, reference_dict)
