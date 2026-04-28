"""
Tests for os_clock_monitor to increase
coverage.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import tempfile
import unittest
from unittest import mock


from trackingfunctionsdk.common.helpers import (
    constants)
from trackingfunctionsdk.model.dto.osclockstate \
    import OsClockState



class TestOsClockMonitorInit(unittest.TestCase):
    """Test OsClockMonitor init=False paths."""

    def test_init_false(self):
        """Test init with init=False flag."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-test.conf',
            init=False)
        self.assertEqual(
            monitor.phc2sys_instance, 'test')
        self.assertIsNone(monitor.ptp_device)
        self.assertFalse(
            monitor.phc2sys_ha_enabled)

    def test_set_phc2sys_instance(self):
        """Test phc2sys instance name parsing."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-myinst.conf',
            init=False)
        self.assertEqual(
            monitor.phc2sys_instance, 'myinst')

    def test_parse_phc2sys_config(self):
        """Test phc2sys config file parsing."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\ndomainNumber 0\n"
                "[ens1f0]\n")
            config_path = tmp_file.name
        try:
            monitor = OsClockMonitor(
                constants.PHC2SYS_CONFIG_PATH
                + 'phc2sys-t.conf',
                init=False)
            monitor.phc2sys_config = config_path
            monitor.parse_phc2sys_config()
            self.assertIn('global', monitor.config)
        finally:
            os.unlink(config_path)

    def test_check_config_file_interface(self):
        """Test config file interface detection."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\n[ens5f0]\n")
            config_path = tmp_file.name
        try:
            monitor = OsClockMonitor(
                constants.PHC2SYS_CONFIG_PATH
                + 'phc2sys-t.conf',
                init=False)
            monitor.phc2sys_config = config_path
            result = (
                monitor
                ._check_config_file_interface())
            self.assertEqual(result, 'ens5f0')
        finally:
            os.unlink(config_path)

    def test_check_config_file_missing(self):
        """Test interface check with missing file."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_config = (
            '/nonexistent/file.conf')
        result = (
            monitor._check_config_file_interface())
        self.assertIsNone(result)

    def test_check_config_global_only(self):
        """Test interface check with global only."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\ndomainNumber 0\n")
            config_path = tmp_file.name
        try:
            monitor = OsClockMonitor(
                constants.PHC2SYS_CONFIG_PATH
                + 'phc2sys-t.conf',
                init=False)
            monitor.phc2sys_config = config_path
            result = (
                monitor
                ._check_config_file_interface())
            self.assertIsNone(result)
        finally:
            os.unlink(config_path)

    def test_get_os_clock_offset_no_device(self):
        """Test offset with no PTP device."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.ptp_device = None
        monitor.phc2sys_ha_enabled = False
        monitor.get_os_clock_offset()
        self.assertEqual(monitor.offset, "0")

    @mock.patch(
        'subprocess.check_output',
        return_value=b'offset 12345ns')
    def test_get_os_clock_offset_success(
            self, mock_subprocess):
        """Test successful offset retrieval.

        mock_subprocess -- mocked check_output
        """
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.ptp_device = 'ptp0'
        monitor.phc2sys_ha_enabled = False
        monitor.get_os_clock_offset()
        self.assertIsNotNone(monitor.offset)

    @mock.patch(
        'subprocess.check_output',
        side_effect=OSError("device error"))
    def test_get_os_clock_offset_error(
            self, mock_subprocess):
        """Test offset retrieval on error.

        mock_subprocess -- mocked check_output
        """
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.ptp_device = 'ptp0'
        monitor.phc2sys_ha_enabled = False
        monitor.get_os_clock_offset()
        self.assertEqual(monitor.offset, "0")

    def test_set_os_clock_state_freerun(self):
        """Test freerun state on high offset."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        high_offset = (
            constants.PHC2SYS_TOLERANCE_HIGH
            + 1000)
        monitor.offset = str(high_offset)
        monitor.phc2sys_tolerance_high = (
            constants.PHC2SYS_TOLERANCE_HIGH)
        monitor.phc2sys_tolerance_low = (
            constants.PHC2SYS_TOLERANCE_LOW)
        monitor.phc2sys_ha_enabled = False
        monitor.set_os_clock_state()
        self.assertEqual(
            monitor.get_os_clock_state(),
            OsClockState.Freerun)

    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.ptpsync.check_critical_resources',
        return_value=(True, True, True, True))
    def test_set_os_clock_state_locked(
            self, mock_critical_resources):
        """Test locked state on normal offset.

        mock_critical_resources -- mocked check
        """
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        tolerance_mid = (
            constants.PHC2SYS_TOLERANCE_LOW
            + constants.PHC2SYS_TOLERANCE_HIGH
        ) // 2
        monitor.offset = str(tolerance_mid)
        monitor.phc2sys_tolerance_high = (
            constants.PHC2SYS_TOLERANCE_HIGH)
        monitor.phc2sys_tolerance_low = (
            constants.PHC2SYS_TOLERANCE_LOW)
        monitor.phc2sys_ha_enabled = False
        monitor.set_os_clock_state()
        self.assertEqual(
            monitor.get_os_clock_state(),
            OsClockState.Locked)

    def test_get_source_ptp_device(self):
        """Test get_source_ptp_device returns dev."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.ptp_device = 'ptp1'
        self.assertEqual(
            monitor.get_source_ptp_device(),
            'ptp1')

    def test_get_time_source_no_interface(self):
        """Test time source with no interface."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.phc2sys_config = (
            '/nonexistent.conf')
        monitor.get_os_clock_time_source(
            '/nonexistent/')
        self.assertEqual(
            monitor._state, OsClockState.Freerun)

    def test_os_clock_status_freerun(self):
        """Test freerun to freerun transition."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.ptp_device = None
        monitor.phc2sys_ha_enabled = False
        monitor.offset = "0"
        monitor.phc2sys_tolerance_high = (
            constants.PHC2SYS_TOLERANCE_HIGH)
        monitor.phc2sys_tolerance_low = (
            constants.PHC2SYS_TOLERANCE_LOW)
        monitor.holdover_time = 30
        monitor.phc2sys_config = (
            '/nonexistent.conf')
        monitor.config = {}
        with mock.patch.object(
                monitor, 'set_utc_offset'):
            new_event, state, _ = (
                monitor.os_clock_status(
                    30, 2,
                    constants.FREERUN_PHC_STATE,
                    0))
        self.assertEqual(
            state, OsClockState.Freerun)

    def test_os_clock_status_to_holdover(self):
        """Test locked to holdover transition."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        import time
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.ptp_device = None
        monitor.phc2sys_ha_enabled = False
        monitor.offset = "0"
        monitor.phc2sys_tolerance_high = (
            constants.PHC2SYS_TOLERANCE_HIGH)
        monitor.phc2sys_tolerance_low = (
            constants.PHC2SYS_TOLERANCE_LOW)
        monitor.holdover_time = 30
        monitor.phc2sys_config = (
            '/nonexistent.conf')
        monitor.config = {}
        with mock.patch.object(
                monitor, 'set_utc_offset'):
            new_event, state, _ = (
                monitor.os_clock_status(
                    30, 2,
                    constants.LOCKED_PHC_STATE,
                    time.time()))
        self.assertEqual(
            state, OsClockState.Holdover)

    def test_get_cmd_line_option_missing(self):
        """Test command line option missing."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        result = (
            monitor
            ._get_phc2sys_command_line_option(
                '/nonexistent/', '-s'))
        self.assertIsNone(result)

    def test_get_interface_phc_device(self):
        """Test PHC device for interface."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc_interface = (
            'nonexistent-iface')
        result = (
            monitor._get_interface_phc_device())
        self.assertIsNone(result)

    def test_set_utc_offset_no_config(self):
        """Test UTC offset with no config."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        import configparser
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.phc_interface = 'ens1f0'
        monitor.phc2sys_tolerance_threshold = (
            1000)
        monitor.config = configparser.ConfigParser(
            delimiters=' ')
        monitor.set_utc_offset('/nonexistent/')
        self.assertIsNotNone(
            monitor.phc2sys_tolerance_low)
        self.assertIsNotNone(
            monitor.phc2sys_tolerance_high)

    def test_query_phc2sys_socket_none(self):
        """Test socket query with None socket."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        result = monitor.query_phc2sys_socket(
            'test', None)
        self.assertIsNone(result)

    def test_query_phc2sys_socket_bad_path(self):
        """Test socket query with bad path."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        result = monitor.query_phc2sys_socket(
            'test', '/nonexistent.sock')
        self.assertIsNone(result)

    def test_set_ha_interface_no_valid(self):
        """Test HA interface with no valid iface."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.phc2sys_com_socket = None
        monitor.valid_phc_interfaces = None
        monitor.phc_interface = None
        with mock.patch.object(
                monitor,
                'query_phc2sys_socket',
                return_value='None'):
            monitor \
                .set_phc2sys_ha_interface_and_phc()
        self.assertEqual(
            monitor._state, OsClockState.Freerun)


if __name__ == '__main__':
    unittest.main()
