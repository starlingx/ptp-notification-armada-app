#
# Copyright (c) 2022-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import os
import unittest
from unittest.mock import mock_open

import mock

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.model.dto.osclockstate import OsClockState

testpath = os.environ.get("TESTPATH", "")
phc2sys_test_config = constants.PTP_CONFIG_PATH + "phc2sys-phc2sys-test.conf"

class OsClockMonitorTests(unittest.TestCase):
    clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)

    def test_set_phc2sys_instance(self):
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.set_phc2sys_instance()
        assert self.clockmon.phc2sys_instance == "phc2sys-test"

    def test_parse_phc2sys_config(self):
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.phc2sys_config = testpath + "test_input_files/phc2sys-test.conf"
        self.clockmon.parse_phc2sys_config()
        assert 'ha_enabled' not in self.clockmon.config['global'].keys()

        self.clockmon.phc2sys_config = testpath + "test_input_files/phc2sys-ha-test.conf"
        self.clockmon.parse_phc2sys_config()
        assert 'ha_enabled' in self.clockmon.config['global'].keys()

    def test_check_config_file_interface(self):
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.phc2sys_config = testpath + "test_input_files/phc2sys-test.conf"
        self.assertEqual(self.clockmon._check_config_file_interface(), "ens2f0")

    @mock.patch('trackingfunctionsdk.common.helpers.os_clock_monitor.open', new_callable=mock_open,
                read_data="101")
    def test_check_command_line_interface(self, mo):
        # Use mock to return the expected readline values
        # Success path
        handlers = (mo.return_value,
                    mock_open(read_data="/usr/sbin/phc2sys\x00-f\x00/etc"
                                        "/ptpinstance/phc2sys-phc "
                                        "-inst1.conf\x00-w\x00-s\x00ens1f0\x00").return_value)
        mo.side_effect = handlers
        self.assertEqual(self.clockmon._get_phc2sys_command_line_option("/var/run/", "-s"), "ens1f0")

        # Failure path - no interface in command line params
        handlers = (mo.return_value,
                    mock_open(read_data="/usr/sbin/phc2sys\x00-f\x00/etc/ptpinstance/phc2sys-phc"
                                        "-inst1.conf\x00-w\x00").return_value)
        mo.side_effect = handlers
        self.assertEqual(self.clockmon._get_phc2sys_command_line_option("/var/run/", "-s"), None)

    @mock.patch('trackingfunctionsdk.common.helpers.os_clock_monitor.glob',
                side_effect=[['/hostsys/class/net/ens1f0/device/ptp/ptp0'],
                             ['/hostsys/class/net/ens1f0/device/ptp/ptp0',
                              '/hostsys/class/net/ens1f0/device/ptp/ptp1'],
                             [],
                             []
                             ])
    def test_get_interface_phc_device(self, glob_patched):
        # Success path
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.phc_interface = "ens1f0"
        self.assertEqual(self.clockmon._get_interface_phc_device(), 'ptp0')

        # Fail path #1 - multiple devices found
        self.assertEqual(self.clockmon._get_interface_phc_device(), None)

        # Fail path #2 - no devices found
        self.assertEqual(self.clockmon._get_interface_phc_device(), None)

    @mock.patch('trackingfunctionsdk.common.helpers.os_clock_monitor.subprocess.check_output',
                side_effect=[b'-37000000015ns'])
    def test_get_os_clock_offset(self, subprocess_patched):
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.ptp_device = 'ptp0'
        self.clockmon.get_os_clock_offset()
        assert self.clockmon.offset == '37000000015'

    def test_set_os_closck_state(self):
        self.clockmon = OsClockMonitor(phc2sys_config=phc2sys_test_config, init=False)
        self.clockmon.offset = '37000000015'
        self.clockmon.set_os_clock_state()
        self.assertEqual(self.clockmon.get_os_clock_state(), OsClockState.Locked)

        # TODO Test for handling clock state change to LOCKED and FREERUN
