#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import mock
import os
import unittest

from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor

testpath = os.environ.get("TESTPATH", "")

holdover_seconds = 15
poll_freq_seconds = 15
phc2sys_service_name = "phc-inst1"
ptp4l_instance = "ptp-inst1"


class PtpMonitorTests(unittest.TestCase):

    def test_check_config_file_interfaces(self):
        self.ptpmon = PtpMonitor(
            ptp4l_instance,
            holdover_seconds,
            poll_freq_seconds,
            phc2sys_service_name,
            init=False,
        )
        self.ptpmon.ptp4l_config = testpath + "test_input_files/ptp4l-ptp-inst1.conf"
        self.assertEqual(
            self.ptpmon._check_config_file_interfaces(), ["enp81s0f3", "enp81s0f4"]
        )

    def test_set_ptp_devices(self):
        self.ptpmon = PtpMonitor(
            ptp4l_instance,
            holdover_seconds,
            poll_freq_seconds,
            phc2sys_service_name,
            init=False,
        )
        self.ptpmon.ptp4l_config = testpath + "test_input_files/ptp4l-ptp-inst1.conf"

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob", return_value=[]
        ):
            self.ptpmon.set_ptp_devices()
        self.assertEqual(self.ptpmon.get_ptp_devices(), [])

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob",
            side_effect=[
                ["/hostsys/class/net/enp81s0f3/device/ptp/ptp0"],
                ["/hostsys/class/net/enp81s0f4/device/ptp/ptp1"],
            ],
        ):
            self.ptpmon.set_ptp_devices()
        self.assertEqual(set(self.ptpmon.get_ptp_devices()), set(["ptp0", "ptp1"]))

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob",
            side_effect=[
                ["/hostsys/class/net/enp81s0f3/device/ptp/ptp0"],
                ["/hostsys/class/net/enp81s0f4/device/ptp/ptp0"],
            ],
        ):
            self.ptpmon.set_ptp_devices()

        self.assertEqual(self.ptpmon.get_ptp_devices(), ["ptp0"])
