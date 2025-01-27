#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import mock
import os
import unittest

from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor

testpath = os.environ.get("TESTPATH", "")


class GnssMonitorTests(unittest.TestCase):

    def test_check_config_file_interfaces(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        self.gnssmon = GnssMonitor(gnss_config, cgu_path = cgu_path)
        self.assertEqual(self.gnssmon._check_config_file_interfaces(), ['ens1f0', 'ens2f0'])

    def test_set_ptp_devices(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                return_value=[]):
            self.gnssmon = GnssMonitor(gnss_config, cgu_path = cgu_path)
        self.assertEqual(self.gnssmon.get_ptp_devices(),[])

        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                side_effect=[['/hostsys/class/net/ens1f0/device/ptp/ptp0'],
                             ['/hostsys/class/net/ens2f0/device/ptp/ptp1']
                             ]):
            self.gnssmon.set_ptp_devices()

        self.assertEqual(set(self.gnssmon.get_ptp_devices()),set(['ptp0','ptp1']))

        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                side_effect=[['/hostsys/class/net/ens1f0/device/ptp/ptp0'],
                             ['/hostsys/class/net/ens2f0/device/ptp/ptp0']
                             ]):
            self.gnssmon.set_ptp_devices()

        self.assertEqual(self.gnssmon.get_ptp_devices(),['ptp0'])
