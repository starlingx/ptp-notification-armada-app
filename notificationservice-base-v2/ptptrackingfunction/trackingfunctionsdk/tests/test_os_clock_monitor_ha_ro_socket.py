#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Unit tests for the phc2sys HA read-only socket resolution.
"""
import configparser
import unittest
from unittest import mock

from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor

MODULE = 'trackingfunctionsdk.common.helpers.os_clock_monitor'
CONFIG_PATH = '/ptp/ptpinstance/phc2sys-ha-test.conf'


def make_monitor(com_socket='/var/run/phc0', ro_socket=None):
    with mock.patch(MODULE + '.constants.PHC2SYS_CONFIG_PATH',
                    '/ptp/ptpinstance/'):
        monitor = OsClockMonitor(CONFIG_PATH, init=False)
    text = "[global]\nha_enabled 1\n"
    if com_socket is not None:
        text += "ha_phc2sys_com_socket %s\n" % com_socket
    if ro_socket is not None:
        text += "ha_phc2sys_com_ro_socket %s\n" % ro_socket
    cfg = configparser.ConfigParser(delimiters=' ')
    cfg.read_string(text)
    monitor.config = cfg
    monitor.phc2sys_ha_enabled = True
    monitor.phc2sys_com_socket = com_socket
    return monitor


class ResolveHaRoSocketTests(unittest.TestCase):

    def test_option_present_in_file_wins(self):
        monitor = make_monitor('/var/run/phc0', '/var/run/custom-ro')
        with mock.patch('os.path.exists', return_value=True):
            self.assertEqual(monitor._resolve_ha_ro_socket(),
                             '/var/run/custom-ro')

    def test_derived_path_used_when_it_exists(self):
        monitor = make_monitor('/var/run/phc0')
        with mock.patch('os.path.exists',
                        side_effect=lambda p: p == '/var/run/phc0ro'):
            self.assertEqual(monitor._resolve_ha_ro_socket(),
                             '/var/run/phc0ro')

    def test_fallback_to_control_socket(self):
        monitor = make_monitor('/var/run/phc0')
        with mock.patch('os.path.exists', return_value=False):
            self.assertEqual(monitor._resolve_ha_ro_socket(),
                             '/var/run/phc0')

    def test_no_sockets_configured_returns_none(self):
        monitor = make_monitor(None)
        self.assertIsNone(monitor._resolve_ha_ro_socket())


if __name__ == '__main__':
    unittest.main()
