"""
Final coverage push tests for daemon publish,
ptp_monitor ptpsync, and os_clock.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import json
import time
import tempfile
import threading
import unittest
from unittest import mock


from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.model.dto.osclockstate import (
    OsClockState)
from trackingfunctionsdk.model.dto.overallclockstate import (
    OverallClockState)


def _build_daemon_context():
    """Build a daemon context JSON string.

    Returns JSON string with PTP daemon config.
    """
    return json.dumps({
        'PTP4L_INSTANCES': ['inst1'],
        'GNSS_INSTANCES': ['ginst1'],
        'GNSS_CONFIGS': ['/tmp/g.conf'],
        'PHC2SYS_CONFIG':
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-phc2sys-t.conf',
        'PHC2SYS_SERVICE_NAME': 'phc2sys-t',
        'THIS_NODE_NAME': 'ctrl-0',
        'THIS_NAMESPACE': 'notification',
        'NOTIFICATION_TRANSPORT_ENDPOINT':
            'rabbit://a:a@127.0.0.1:5672/',
        'REGISTRATION_TRANSPORT_ENDPOINT':
            'rabbit://a:a@127.0.0.1:5672/',
    })


@mock.patch(
    'trackingfunctionsdk.services.daemon'
    '.PtpEventProducer')
@mock.patch(
    'trackingfunctionsdk.services.daemon'
    '.OsClockMonitor')
@mock.patch(
    'trackingfunctionsdk.services.daemon'
    '.PtpMonitor')
@mock.patch(
    'trackingfunctionsdk.services.daemon'
    '.GnssMonitor')
def _create_ptp_watcher(
        mock_gnss, mock_ptp,
        mock_osclock, mock_producer):
    """Create a PtpWatcherDefault with mocked deps.

    mock_gnss -- mocked GnssMonitor class
    mock_ptp -- mocked PtpMonitor class
    mock_osclock -- mocked OsClockMonitor class
    mock_producer -- mocked PtpEventProducer class

    Returns PtpWatcherDefault instance.
    """
    from trackingfunctionsdk.services.daemon import (
        PtpWatcherDefault)
    return PtpWatcherDefault(
        threading.Event(), '{}',
        _build_daemon_context())


class TestDaemonPublishAll(unittest.TestCase):
    """Test all publish methods with mock setup."""

    def test_publish_gnss_forced(self):
        """Test forced GNSS status publish."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.get_gnss_status.return_value = (
            True, GnssState.Synchronized,
            time.time())
        gnss_monitor.ts2phc_service_name = 'ginst1'
        publish_gnss = (
            watcher
            ._PtpWatcherDefault__publish_gnss_status)
        publish_gnss(forced=True)
        self.assertTrue(
            watcher.ptpeventproducer
            .publish_status.called)

    def test_publish_gnss_no_event(self):
        """Test GNSS publish with no new event."""
        watcher = _create_ptp_watcher()
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.get_gnss_status.return_value = (
            False, GnssState.Failure_Nofix,
            time.time())
        gnss_monitor.ts2phc_service_name = 'ginst1'
        publish_gnss = (
            watcher
            ._PtpWatcherDefault__publish_gnss_status)
        publish_gnss(forced=False)
        watcher.ptpeventproducer.publish_status.assert_not_called()

    def test_publish_os_clock_new_event(self):
        """Test OS clock publish on new event."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        watcher.os_clock_monitor \
            .os_clock_status.return_value = (
                True, OsClockState.Locked,
                time.time())
        publish_os = (
            watcher
            ._PtpWatcherDefault__publish_os_clock_status)
        publish_os(forced=False)
        self.assertTrue(
            watcher.ptpeventproducer
            .publish_status.called)

    def test_publish_overall_new_event(self):
        """Test overall sync status publish."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Freerun)
        publish_overall = (
            watcher._PtpWatcherDefault__publish_overall_sync_status)
        publish_overall(forced=False)
        watcher.os_clock_monitor.get_os_clock_state.assert_called()

    @mock.patch.dict(
        os.environ,
        {'NOTIFICATION_FORMAT': 'legacy'})
    def test_publish_os_clock_legacy_format(self):
        """Test OS clock publish in legacy format."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        watcher.os_clock_monitor \
            .os_clock_status.return_value = (
                True, OsClockState.Locked,
                time.time())
        publish_os = (
            watcher
            ._PtpWatcherDefault__publish_os_clock_status)
        publish_os(forced=True)
        watcher.ptpeventproducer.publish_status.assert_called()

    def test_publish_ptp_no_event_no_forced(self):
        """Test PTP publish with no event."""
        watcher = _create_ptp_watcher()
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_sync_state \
            .return_value = None
        ptp_monitor.get_ptp_sync_state \
            .return_value = (
                False, PtpState.Freerun,
                time.time())
        ptp_monitor.get_ptp_clock_class \
            .return_value = (
                False, '248', time.time())
        ptp_monitor.ptp4l_service_name = 'inst1'
        watcher.ptp_device_simulated = False
        publish_ptp = (
            watcher
            ._PtpWatcherDefault__publish_ptpstatus)
        publish_ptp(forced=False)
        watcher.ptpeventproducer.publish_status.assert_not_called()


class TestPtpMonitorPtpsync(unittest.TestCase):
    """Test ptp_monitor.ptpsync with mocked pmc."""

    @mock.patch(
        'trackingfunctionsdk.common.helpers'
        '.ptpsync.run_shell2')
    def test_ptpsync(self, mock_shell):
        """Test ptpsync parses PMC output.

        mock_shell -- mocked run_shell2 function
        """
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor.ptp4l_service_name = 'x'
        monitor.domain_number = 0
        monitor.uds_address = '/var/run/ptp4l-x'
        pmc_out = (
            b"portState slave\\n\\t\\t"
            b"gmPresent true\\n\\t\\t"
            b"master_offset 50\\n\\t\\t"
            b"gm.ClockClass 6\\n\\t\\t"
            b"grandmasterIdentity gm1\\n\\t\\t"
            b"timeTraceable 1\\n\\t\\t"
            b"clockIdentity clk1\\n\\t\\t"
            b"clockClass 6"
        )
        mock_shell.return_value = (
            pmc_out, b'', 0)
        result, total, port_count = (
            monitor.ptpsync())
        self.assertIsInstance(result, dict)
        self.assertGreater(total, 0)

    def test_ptp_status_with_resources(self):
        """Test ptp_status with available resources."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = PtpState.Freerun
        monitor._ptp_event_time = time.time()
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.holdover_time = 30
        monitor.offset_threshold = 1000000
        monitor.sync_source = (
            constants.ClockSourceType.TypeNA)
        ptpsync_result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY: 'gm1',
            constants.CLOCK_IDENTITY: 'clk2',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'slave',
        }
        with mock.patch(
                'trackingfunctionsdk.common.helpers'
                '.ptpsync.check_critical_resources',
                return_value=(
                    True, True, True, True)), \
             mock.patch.object(
                monitor, 'ptpsync',
                return_value=(
                    ptpsync_result, 8, 1)):
            new_event, state, _ = (
                monitor.ptp_status())
        self.assertEqual(
            state, constants.LOCKED_PHC_STATE)

    def test_ptp_status_runtime_error(self):
        """Test ptp_status handles RuntimeError."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = PtpState.Locked
        monitor._ptp_event_time = time.time()
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.holdover_time = 30
        monitor.offset_threshold = 1000
        monitor.sync_source = (
            constants.ClockSourceType.TypePTP)
        with mock.patch(
                'trackingfunctionsdk.common.helpers'
                '.ptpsync.check_critical_resources',
                return_value=(
                    True, True, True, True)), \
             mock.patch.object(
                monitor, 'ptpsync',
                return_value=({}, 8, 1)):
            new_event, state, _ = (
                monitor.ptp_status())
        # RuntimeError caught, keeps previous state
        self.assertEqual(state, PtpState.Locked)

    def test_set_ptp_clock_class_retry(self):
        """Test clock class retry decrement."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._clock_class = '6'
        monitor._clock_class_retry = 2
        monitor.pmc_query_results = {}
        monitor.set_ptp_clock_class()
        self.assertEqual(monitor._clock_class, '6')
        self.assertEqual(
            monitor._clock_class_retry, 1)


class TestOsClockMonitorExtended(unittest.TestCase):
    """Cover remaining os_clock_monitor paths."""

    def test_os_clock_status_holdover_expired(self):
        """Test holdover to freerun on expiry."""
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
        monitor.holdover_time = 1
        monitor.phc2sys_config = (
            '/nonexistent.conf')
        monitor.config = {}
        with mock.patch.object(
                monitor, 'set_utc_offset'):
            new_event, state, _ = (
                monitor.os_clock_status(
                    1, 2,
                    constants.HOLDOVER_PHC_STATE,
                    0))
        self.assertEqual(
            state, OsClockState.Freerun)

    def test_os_clock_status_state_changed(self):
        """Test os_clock_status detects change."""
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
                    constants.UNKNOWN_PHC_STATE,
                    0))
        self.assertTrue(new_event)

    def test_set_os_clock_state_not_running(self):
        """Test freerun when phc2sys not running."""
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
        with mock.patch(
                'trackingfunctionsdk.common.helpers'
                '.ptpsync.check_critical_resources',
                return_value=(
                    True, True, False, True)):
            monitor.set_os_clock_state()
        self.assertEqual(
            monitor.get_os_clock_state(),
            OsClockState.Freerun)

    def test_set_os_clock_state_ha_no_valid(self):
        """Test freerun in HA with no valid iface."""
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
        monitor.phc2sys_ha_enabled = True
        monitor.valid_phc_interfaces = 'None'
        with mock.patch(
                'trackingfunctionsdk.common.helpers'
                '.ptpsync.check_critical_resources',
                return_value=(
                    True, True, True, True)):
            monitor.set_os_clock_state()
        self.assertEqual(
            monitor.get_os_clock_state(),
            OsClockState.Freerun)

    def test_get_os_clock_time_source_realtime(self):
        """Test CLOCK_REALTIME source handling."""
        from trackingfunctionsdk.common.helpers \
            .os_clock_monitor import OsClockMonitor
        monitor = OsClockMonitor(
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-t.conf',
            init=False)
        monitor.phc2sys_instance = 't'
        monitor.phc2sys_config = (
            '/nonexistent.conf')
        with mock.patch.object(
                monitor,
                '_get_phc2sys_command_line_option',
                return_value=(
                    constants.CLOCK_REALTIME)):
            monitor.get_os_clock_time_source(
                '/nonexistent/')
        self.assertIsNone(monitor.phc_interface)


if __name__ == '__main__':
    unittest.main()
