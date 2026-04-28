"""
Tests for gnss_monitor and cgu_handler to
increase coverage.
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
from trackingfunctionsdk.model.dto.gnssstate import (
    GnssState)


class TestGnssMonitorCoverage(unittest.TestCase):
    """Tests for GnssMonitor methods."""

    def _create_gnss_monitor(self):
        """Create a GnssMonitor with mocked deps.

        Returns GnssMonitor instance.
        """
        from trackingfunctionsdk.common.helpers \
            .gnss_monitor import GnssMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False,
                prefix='ts2phc-testinst') \
                as tmp_file:
            tmp_file.write(
                "[global]\n"
                "ts2phc.nmea_serialport"
                " /dev/ttyGNSS0\n"
                "[ens1f0]\n")
            config_path = tmp_file.name
        cgu_patch = mock.patch(
            'trackingfunctionsdk.common.helpers'
            '.gnss_monitor.CguHandler')
        phc_patch = mock.patch(
            'trackingfunctionsdk.common.helpers'
            '.gnss_monitor.utils'
            '.get_interface_phc_device',
            return_value='ptp0')
        with mock.patch.object(
                constants,
                'TS2PHC_CONFIG_PATH',
                '/tmp/'), \
             cgu_patch as mock_cgu, \
             phc_patch:
            mock_cgu_instance = (
                mock_cgu.return_value)
            mock_cgu_instance.read_cgu \
                .return_value = None
            mock_cgu_instance.get_eec_current_ref \
                .return_value = 'GNSS-1PPS'
            mock_cgu_instance.get_eec_pin_type \
                .return_value = 'gnss'
            mock_cgu_instance.get_eec_status \
                .return_value = 'locked-ho-acq'
            mock_cgu_instance.get_pps_current_ref \
                .return_value = 'GNSS-1PPS'
            mock_cgu_instance.get_pps_pin_type \
                .return_value = 'gnss'
            mock_cgu_instance.get_pps_status \
                .return_value = 'locked-ho-acq'
            monitor = GnssMonitor(
                config_path,
                nmea_serialport='/dev/ttyGNSS0')
        self._tmpfile = config_path
        return monitor

    def tearDown(self):
        """Clean up temporary files."""
        if hasattr(self, '_tmpfile') and \
                os.path.exists(self._tmpfile):
            os.unlink(self._tmpfile)

    def test_init(self):
        """Test GnssMonitor initialization."""
        monitor = self._create_gnss_monitor()
        self.assertIsNotNone(monitor)
        self.assertIsNotNone(monitor.ptp_devices)

    def test_get_ptp_devices(self):
        """Test get_ptp_devices returns list."""
        monitor = self._create_gnss_monitor()
        self.assertIn(
            'ptp0', monitor.get_ptp_devices())

    def test_check_config_file_interfaces(self):
        """Test config file interface parsing."""
        monitor = self._create_gnss_monitor()
        result = (
            monitor
            ._check_config_file_interfaces())
        self.assertIn('ens1f0', result)

    def test_check_config_file_missing(self):
        """Test interface check missing file."""
        monitor = self._create_gnss_monitor()
        monitor.config_file = (
            '/nonexistent.conf')
        result = (
            monitor
            ._check_config_file_interfaces())
        self.assertEqual(result, [])

    def test_set_gnss_status_no_pid(self):
        """Test GNSS status with no PID file."""
        monitor = self._create_gnss_monitor()
        monitor.ts2phc_service_name = (
            'nonexistent')
        monitor.set_gnss_status()
        self.assertEqual(
            monitor._state,
            GnssState.Failure_Nofix)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_set_gnss_status_locked(
            self, mock_isfile):
        """Test GNSS status locked state.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        cgu = monitor.gnss_cgu_handler
        cgu.read_cgu.return_value = None
        cgu.get_eec_status.return_value = (
            constants.GNSS_LOCKED_HO_ACQ)
        cgu.get_pps_status.return_value = (
            constants.GNSS_LOCKED_HO_ACQ)
        monitor.set_gnss_status()
        self.assertEqual(
            monitor._state,
            GnssState.Synchronized)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_set_gnss_status_unlocked(
            self, mock_isfile):
        """Test GNSS status unlocked state.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        cgu = monitor.gnss_cgu_handler
        cgu.read_cgu.return_value = None
        cgu.get_eec_status.return_value = (
            'unlocked')
        cgu.get_pps_status.return_value = (
            'unlocked')
        monitor.set_gnss_status()
        self.assertEqual(
            monitor._state,
            GnssState.Failure_Nofix)

    def test_update(self):
        """Test update method sets status."""
        monitor = self._create_gnss_monitor()
        monitor.ts2phc_service_name = (
            'nonexistent')
        monitor.update(None, "test event")
        self.assertEqual(
            monitor._state,
            GnssState.Failure_Nofix)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_get_gnss_status_synchronized(
            self, mock_isfile):
        """Test GNSS status synchronized.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        cgu = monitor.gnss_cgu_handler
        cgu.get_eec_status.return_value = (
            constants.GNSS_LOCKED_HO_ACQ)
        cgu.get_pps_status.return_value = (
            constants.GNSS_LOCKED_HO_ACQ)
        new_event, state, _ = (
            monitor.get_gnss_status(
                GnssState.Failure_Nofix, 0))
        self.assertEqual(
            state, GnssState.Synchronized)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_get_gnss_holdover_from_sync(
            self, mock_isfile):
        """Test holdover from synchronized.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        cgu = monitor.gnss_cgu_handler
        cgu.get_eec_status.return_value = (
            'unlocked')
        cgu.get_pps_status.return_value = (
            'unlocked')
        new_event, state, _ = (
            monitor.get_gnss_status(
                GnssState.Synchronized, 0))
        self.assertEqual(
            state, GnssState.Holdover)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_get_gnss_failure_from_freerun(
            self, mock_isfile):
        """Test failure from freerun state.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        cgu = monitor.gnss_cgu_handler
        cgu.get_eec_status.return_value = (
            'unlocked')
        cgu.get_pps_status.return_value = (
            'unlocked')
        new_event, state, _ = (
            monitor.get_gnss_status(
                GnssState.Failure_Nofix, 0))
        self.assertEqual(
            state, GnssState.Failure_Nofix)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_get_gnss_holdover_expired(
            self, mock_isfile):
        """Test holdover expiry to failure.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        monitor.holdover_time = 1
        cgu = monitor.gnss_cgu_handler
        cgu.get_eec_status.return_value = (
            'unlocked')
        cgu.get_pps_status.return_value = (
            'unlocked')
        import time
        old_time = time.time() - 100
        new_event, state, _ = (
            monitor.get_gnss_status(
                GnssState.Holdover, old_time))
        self.assertEqual(
            state, GnssState.Failure_Nofix)

    @mock.patch(
        'os.path.isfile', return_value=True)
    def test_get_gnss_holdover_remaining(
            self, mock_isfile):
        """Test holdover with time remaining.

        mock_isfile -- mocked os.path.isfile
        """
        monitor = self._create_gnss_monitor()
        monitor.holdover_time = 9999
        cgu = monitor.gnss_cgu_handler
        cgu.get_eec_status.return_value = (
            'unlocked')
        cgu.get_pps_status.return_value = (
            'unlocked')
        import datetime
        now = (
            datetime.datetime.utcnow()
            .timestamp())
        monitor._event_time = now
        monitor._sync_state = GnssState.Holdover
        new_event, state, _ = (
            monitor.get_gnss_status())
        self.assertEqual(
            state, GnssState.Holdover)


class TestCguHandlerCoverage(unittest.TestCase):
    """Tests for CguHandler."""

    def test_init(self):
        """Test CguHandler initialization."""
        from trackingfunctionsdk.common.helpers \
            .cgu_handler import CguHandler
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\n"
                "ts2phc.nmea_serialport"
                " /dev/ttyGNSS0\n")
            config_path = tmp_file.name
        try:
            handler = CguHandler(
                config_path,
                nmea_serialport='/dev/ttyGNSS0')
            self.assertIsNotNone(handler)
        finally:
            os.unlink(config_path)

    def test_prune_reconfigured_suffix(self):
        """Test suffix pruning from device path."""
        from trackingfunctionsdk.common.helpers \
            .cgu_handler import CguHandler
        handler = CguHandler.__new__(CguHandler)
        result = (
            handler._prune_reconfigured_suffix(
                '/dev/ttyGNSS0.pty'))
        self.assertEqual(
            result, '/dev/ttyGNSS0')

    def test_prune_reconfigured_suffix_none(self):
        """Test suffix pruning with None input."""
        from trackingfunctionsdk.common.helpers \
            .cgu_handler import CguHandler
        handler = CguHandler.__new__(CguHandler)
        result = (
            handler._prune_reconfigured_suffix(
                None))
        self.assertIsNone(result)

    def test_get_gnss_nmea_from_config(self):
        """Test NMEA serial port from config."""
        from trackingfunctionsdk.common.helpers \
            .cgu_handler import CguHandler
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\n"
                "ts2phc.nmea_serialport"
                " /dev/ttyGNSS_1800_0\n")
            config_path = tmp_file.name
        try:
            handler = (
                CguHandler.__new__(CguHandler))
            handler._config_file = config_path
            get_nmea = (
                handler
                ._get_gnss_nmea_serialport_from_ts2phc_config)
            get_nmea()
            self.assertEqual(
                handler._nmea_serialport,
                '/dev/ttyGNSS_1800_0')
        finally:
            os.unlink(config_path)

    def test_get_gnss_nmea_missing_file(self):
        """Test NMEA config with missing file."""
        from trackingfunctionsdk.common.helpers \
            .cgu_handler import CguHandler
        handler = CguHandler.__new__(CguHandler)
        handler._config_file = (
            '/nonexistent.conf')
        with self.assertRaises(
                FileNotFoundError):
            get_nmea = (
                handler
                ._get_gnss_nmea_serialport_from_ts2phc_config)
            get_nmea()


if __name__ == '__main__':
    unittest.main()
