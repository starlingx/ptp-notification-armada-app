"""
Extended daemon tests for publish methods
and request handler.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import json
import time
import threading
import unittest
from unittest import mock


from trackingfunctionsdk.common.helpers import (
    constants)
from trackingfunctionsdk.model.dto.ptpstate import (
    PtpState)
from trackingfunctionsdk.model.dto.gnssstate import (
    GnssState)
from trackingfunctionsdk.model.dto.osclockstate import (
    OsClockState)
from trackingfunctionsdk.model.dto.overallclockstate \
    import OverallClockState


def _build_daemon_context():
    """Build a daemon context JSON string.

    Returns JSON string with PTP daemon config.
    """
    return json.dumps({
        'PTP4L_INSTANCES': ['ptp-inst1'],
        'GNSS_INSTANCES': ['gnss-inst1'],
        'GNSS_CONFIGS': ['/tmp/gnss.conf'],
        'PHC2SYS_CONFIG':
            constants.PHC2SYS_CONFIG_PATH
            + 'phc2sys-phc2sys-test.conf',
        'PHC2SYS_SERVICE_NAME': 'phc2sys-test',
        'THIS_NODE_NAME': 'controller-0',
        'THIS_NAMESPACE': 'notification',
        'NOTIFICATION_TRANSPORT_ENDPOINT':
            'rabbit://admin:admin@127.0.0.1'
            ':5672/',
        'REGISTRATION_TRANSPORT_ENDPOINT':
            'rabbit://admin:admin@127.0.0.1'
            ':5672/',
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
    event = threading.Event()
    return PtpWatcherDefault(
        event, '{}', _build_daemon_context())


class TestDaemonPublishPtp(unittest.TestCase):
    """Test __publish_ptpstatus."""

    def test_publish_ptpstatus_no_event(self):
        """Test PTP publish with no new event."""
        watcher = _create_ptp_watcher()
        watcher.ptp_monitor_list = [
            mock.MagicMock()]
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
        ptp_monitor.ptp4l_service_name = (
            'ptp-inst1')
        watcher.ptp_device_simulated = False
        publish_ptp = (
            watcher
            ._PtpWatcherDefault__publish_ptpstatus)
        publish_ptp(forced=False)
        watcher.ptpeventproducer.publish_status.assert_not_called()


class TestDaemonPublishGnss(unittest.TestCase):
    """Test __publish_gnss_status."""

    def test_publish_gnss_forced(self):
        """Test forced GNSS status publish."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.get_gnss_status \
            .return_value = (
                True, GnssState.Synchronized,
                time.time())
        gnss_monitor.ts2phc_service_name = (
            'gnss-inst1')
        publish_gnss = (
            watcher
            ._PtpWatcherDefault__publish_gnss_status)
        publish_gnss(forced=True)
        watcher.ptpeventproducer \
            .publish_status.assert_called()


class TestDaemonPublishOsClock(unittest.TestCase):
    """Test __publish_os_clock_status."""

    def test_publish_os_clock_forced(self):
        """Test forced OS clock status publish."""
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
        watcher.ptpeventproducer \
            .publish_status.assert_called()

    def test_publish_os_clock_no_event(self):
        """Test OS clock publish with no event."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .os_clock_status.return_value = (
                False, OsClockState.Freerun,
                time.time())
        publish_os = (
            watcher
            ._PtpWatcherDefault__publish_os_clock_status)
        publish_os(forced=False)
        watcher.ptpeventproducer.publish_status.assert_not_called()


class TestDaemonPublishOverall(unittest.TestCase):
    """Test __publish_overall_sync_status."""

    def test_publish_overall_forced(self):
        """Test forced overall sync publish."""
        watcher = _create_ptp_watcher()
        watcher.ptpeventproducer.publish_status \
            .return_value = (True, True)
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Freerun)
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = None
        publish_overall = (
            watcher._PtpWatcherDefault__publish_overall_sync_status)
        publish_overall(forced=True)
        watcher.ptpeventproducer \
            .publish_status.assert_called()


class TestDaemonOverallSyncState(unittest.TestCase):
    """Test __get_overall_sync_state paths."""

    def test_overall_locked_via_gnss(self):
        """Test overall locked via GNSS source."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Locked)
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = ['ptp0']
        gnss_monitor.ts2phc_service_name = (
            'gnss-inst1')
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_devices \
            .return_value = None
        ptp_monitor.get_ptp_devices \
            .return_value = []
        ptp_monitor.get_ptp_sync_source \
            .return_value = (
                constants.ClockSourceType.TypeNA)
        get_gnss = (
            watcher
            ._PtpWatcherDefault__get_primary_gnss_state)
        get_ptp = (
            watcher
            ._PtpWatcherDefault__get_primary_ptp_state)
        watcher._PtpWatcherDefault__get_primary_gnss_state = (
            mock.MagicMock(return_value=(
                gnss_monitor,
                GnssState.Synchronized)))
        watcher._PtpWatcherDefault__get_primary_ptp_state = (
            mock.MagicMock(return_value=(
                None, PtpState.Freerun)))
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            30, 2,
            constants.FREERUN_PHC_STATE,
            time.time())
        self.assertEqual(
            state, OverallClockState.Locked)

    def test_overall_locked_via_ptp(self):
        """Test overall locked via PTP source."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Locked)
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        ptp_monitor = mock.MagicMock()
        ptp_monitor.get_ptp_sync_source \
            .return_value = (
                constants.ClockSourceType.TypePTP)
        watcher._PtpWatcherDefault__get_primary_gnss_state = (
            mock.MagicMock(
                return_value=(None, None)))
        watcher._PtpWatcherDefault__get_primary_ptp_state = (
            mock.MagicMock(return_value=(
                ptp_monitor, PtpState.Locked)))
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            30, 2,
            constants.FREERUN_PHC_STATE,
            time.time())
        self.assertEqual(
            state, OverallClockState.Locked)

    def test_overall_freerun_no_ptp_device(self):
        """Test freerun when no PTP device."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Locked)
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = None
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            30, 2,
            constants.FREERUN_PHC_STATE,
            time.time())
        self.assertEqual(
            state, OverallClockState.Freerun)

    def test_overall_holdover_from_locked(self):
        """Test holdover transition from locked."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Freerun)
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            30, 2,
            constants.LOCKED_PHC_STATE,
            time.time())
        self.assertEqual(
            state, OverallClockState.Holdover)

    def test_overall_holdover_expired(self):
        """Test holdover expiry to freerun."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Freerun)
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            1, 2,
            constants.HOLDOVER_PHC_STATE, 0)
        self.assertEqual(
            state, OverallClockState.Freerun)

    def test_overall_na_source(self):
        """Test freerun with NA clock source."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_os_clock_state.return_value = (
                OsClockState.Locked)
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        watcher._PtpWatcherDefault__get_primary_gnss_state = (
            mock.MagicMock(
                return_value=(None, None)))
        ptp_monitor = mock.MagicMock()
        ptp_monitor.get_ptp_sync_source \
            .return_value = (
                constants.ClockSourceType.TypeNA)
        watcher._PtpWatcherDefault__get_primary_ptp_state = (
            mock.MagicMock(return_value=(
                ptp_monitor, PtpState.Freerun)))
        get_overall = (
            watcher
            ._PtpWatcherDefault__get_overall_sync_state)
        new_event, state, _ = get_overall(
            30, 2,
            constants.FREERUN_PHC_STATE,
            time.time())
        self.assertEqual(
            state, OverallClockState.Freerun)


class TestDaemonCalculateHoldover(unittest.TestCase):
    """Test __calculate_overall_holdover_time."""

    def test_no_ptp_device(self):
        """Test holdover with no PTP device."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = None
        watcher.os_clock_monitor \
            .holdover_time = 30
        calc_holdover = (
            watcher._PtpWatcherDefault__calculate_overall_holdover_time)
        result = calc_holdover()
        self.assertEqual(result, 30)

    def test_gnss_source(self):
        """Test holdover from GNSS source."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        watcher.os_clock_monitor \
            .holdover_time = 30
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = ['ptp0']
        gnss_monitor.holdover_time = 20
        calc_holdover = (
            watcher._PtpWatcherDefault__calculate_overall_holdover_time)
        result = calc_holdover()
        self.assertEqual(result, 20)

    def test_ptp_source(self):
        """Test holdover from PTP source."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        watcher.os_clock_monitor \
            .holdover_time = 30
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = []
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_devices \
            .return_value = None
        ptp_monitor.get_ptp_devices \
            .return_value = ['ptp0']
        ptp_monitor.holdover_time = 25
        calc_holdover = (
            watcher._PtpWatcherDefault__calculate_overall_holdover_time)
        result = calc_holdover()
        self.assertEqual(result, 25)

    def test_no_source_found(self):
        """Test holdover with no source found."""
        watcher = _create_ptp_watcher()
        watcher.os_clock_monitor \
            .get_source_ptp_device \
            .return_value = 'ptp0'
        watcher.os_clock_monitor \
            .holdover_time = 30
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = []
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_devices \
            .return_value = None
        ptp_monitor.get_ptp_devices \
            .return_value = []
        calc_holdover = (
            watcher._PtpWatcherDefault__calculate_overall_holdover_time)
        result = calc_holdover()
        expected = float(
            watcher.overalltracker_context[
                'holdover_seconds'])
        self.assertEqual(result, expected)


class TestDaemonStartStopListener(unittest.TestCase):
    """Test __start_listener and __stop_listener."""

    def test_start_listener(self):
        """Test start_listener calls producer."""
        watcher = _create_ptp_watcher()
        start = (
            watcher
            ._PtpWatcherDefault__start_listener)
        start()
        watcher.ptpeventproducer \
            .start_status_listener \
            .assert_called_once()

    def test_stop_listener(self):
        """Test stop_listener calls producer."""
        watcher = _create_ptp_watcher()
        stop = (
            watcher
            ._PtpWatcherDefault__stop_listener)
        stop()
        watcher.ptpeventproducer \
            .stop_status_listener \
            .assert_called_once()


class TestDaemonRequestHandler(unittest.TestCase):
    """Test PtpRequestHandlerDefault."""

    def test_build_event_response(self):
        """Test event response for lock state."""
        watcher = _create_ptp_watcher()
        handler = (
            watcher
            ._PtpWatcherDefault__ptprequest_handler)
        resource_address = (
            '/./' + 'controller-0'
            + constants.SOURCE_SYNC_PTP_LOCK_STATE)
        result = handler._build_event_response(
            constants.SOURCE_SYNC_PTP_LOCK_STATE,
            time.time(),
            resource_address,
            'Locked')
        self.assertIn('id', result)
        self.assertIn('data', result)
        data_type = (
            result['data']['values'][0]
            ['data_type'])
        self.assertEqual(
            data_type,
            constants.DATA_TYPE_NOTIFICATION)

    def test_build_event_response_metric(self):
        """Test event response for clock class."""
        watcher = _create_ptp_watcher()
        handler = (
            watcher
            ._PtpWatcherDefault__ptprequest_handler)
        resource_address = (
            '/./' + 'controller-0'
            + constants
            .SOURCE_SYNC_PTP_CLOCK_CLASS)
        result = handler._build_event_response(
            constants.SOURCE_SYNC_PTP_CLOCK_CLASS,
            time.time(),
            resource_address,
            '6')
        data_type = (
            result['data']['values'][0]
            ['data_type'])
        self.assertEqual(
            data_type,
            constants.DATA_TYPE_METRIC)


class TestDaemonGetPrimaryStates(unittest.TestCase):
    """Test primary PTP and GNSS state getters."""

    def test_get_primary_ptp_state_found(self):
        """Test primary PTP state when found."""
        watcher = _create_ptp_watcher()
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_devices \
            .return_value = None
        ptp_monitor.get_ptp_devices \
            .return_value = ['ptp0']
        ptp_monitor.get_ptp_sync_source \
            .return_value = (
                constants.ClockSourceType.TypePTP)
        ptp_monitor.get_ptp_sync_state \
            .return_value = (
                True, PtpState.Locked,
                time.time())
        get_ptp = (
            watcher
            ._PtpWatcherDefault__get_primary_ptp_state)
        primary, state = get_ptp('ptp0')
        self.assertIsNotNone(primary)
        self.assertEqual(state, PtpState.Locked)

    def test_get_primary_ptp_state_not_found(self):
        """Test primary PTP state when not found."""
        watcher = _create_ptp_watcher()
        ptp_monitor = watcher.ptp_monitor_list[0]
        ptp_monitor.set_ptp_devices \
            .return_value = None
        ptp_monitor.get_ptp_devices \
            .return_value = []
        get_ptp = (
            watcher
            ._PtpWatcherDefault__get_primary_ptp_state)
        primary, state = get_ptp('ptp0')
        self.assertIsNone(primary)
        self.assertEqual(state, PtpState.Freerun)

    def test_get_primary_gnss_state_found(self):
        """Test primary GNSS state when found."""
        watcher = _create_ptp_watcher()
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = ['ptp0']
        gnss_monitor.get_gnss_status \
            .return_value = (
                True, GnssState.Synchronized,
                time.time())
        get_gnss = (
            watcher
            ._PtpWatcherDefault__get_primary_gnss_state)
        primary, state = get_gnss('ptp0')
        self.assertIsNotNone(primary)

    def test_get_primary_gnss_state_not_found(self):
        """Test primary GNSS state not found."""
        watcher = _create_ptp_watcher()
        gnss_monitor = watcher.observer_list[0]
        gnss_monitor.set_ptp_devices \
            .return_value = None
        gnss_monitor.get_ptp_devices \
            .return_value = []
        get_gnss = (
            watcher
            ._PtpWatcherDefault__get_primary_gnss_state)
        primary, state = get_gnss('ptp0')
        self.assertIsNone(primary)


if __name__ == '__main__':
    unittest.main()
