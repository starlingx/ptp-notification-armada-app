#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import unittest
import os
from unittest.mock import MagicMock

from trackingfunctionsdk.common.helpers.dmesg_watcher import DmesgWatcher
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor


testpath = os.environ.get("TESTPATH", "")

class DmesgWatcherTests(unittest.TestCase):
    testDmesgWatcher = DmesgWatcher()
    observer_a = GnssMonitor(testpath + "./test_input_files/ts2phc_valid.conf",
                             "tty_GNSS_1800_0", "0000:18:00.0",
                             testpath + "./test_input_files/mock_cgu_output")
    observer_b = GnssMonitor(testpath + "./test_input_files/ts2phc_valid.conf",
                             "tty_GNSS_1a00_0", "0000:1a:00.0",
                             testpath + "./test_input_files/mock_cgu_output")

    def test_parse_dmesg_event(self):
        self.testDmesgWatcher.attach(self.observer_a)
        self.testDmesgWatcher.notify = MagicMock()
        with open(testpath + "./test_input_files/mock_kern.log", 'r') as dmesg:
            for line in dmesg:
                self.testDmesgWatcher.parse_dmesg_event(line)
        assert self.testDmesgWatcher.notify.called

        # Test that notify is not called when there is no match
        self.testDmesgWatcher.notify.reset_mock()
        self.testDmesgWatcher.attach(self.observer_b)
        with open(testpath + "./test_input_files/mock_kern.log", 'r') as dmesg:
            for line in dmesg:
                self.testDmesgWatcher.parse_dmesg_event(line)
        assert self.testDmesgWatcher.notify.assert_not_called

    def test_attach_detach(self):
        self.testDmesgWatcher.attach(self.observer_a)
        self.testDmesgWatcher.attach(self.observer_b)
        self.assertEqual(len(self.testDmesgWatcher._observers), 2)
        self.testDmesgWatcher.detach(self.observer_a)
        self.testDmesgWatcher.detach(self.observer_b)
        self.assertEqual(len(self.testDmesgWatcher._observers), 0)

    def test_notify(self):
        self.observer_a.update = MagicMock
        self.testDmesgWatcher.notify(observer=self.observer_a,
                        matched_line="2022-06-03T19:50:05.959 controller-0 kernel: warning [    "
                                     "4.635511] ice 0000:18:00.0: <DPLL1> state changed to: "
                                     "locked_ho_ack, pin GNSS-1PPS")
        assert self.observer_a.update.called
