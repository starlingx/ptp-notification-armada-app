"""
Tests for ptp_monitor to increase coverage.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import tempfile
import datetime
import unittest
from unittest import mock


from trackingfunctionsdk.common.helpers import (
    constants)
from trackingfunctionsdk.model.dto.ptpstate import (
    PtpState)


class TestPtpMonitorInit(unittest.TestCase):
    """Test PtpMonitor with init=False."""

    def test_init_false(self):
        """Test init with init=False flag."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'inst1', 30, 'phc2sys-inst1',
            init=False)
        self.assertIsNotNone(monitor)

    def test_init_true(self):
        """Test init with init=True flag."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        with mock.patch.object(
                PtpMonitor, 'set_ptp_devices'), \
             mock.patch.object(
                PtpMonitor,
                'set_ptp_sync_state'), \
             mock.patch.object(
                PtpMonitor,
                'set_ptp_clock_class'):
            monitor = PtpMonitor(
                'inst1', 30, 'phc2sys-inst1')
        self.assertEqual(
            monitor.ptp4l_service_name, 'inst1')
        self.assertEqual(
            monitor.phc2sys_service_name,
            'phc2sys-inst1')
        self.assertIsNotNone(
            monitor.holdover_time)
        self.assertIsNotNone(
            monitor.offset_threshold)

    def test_check_config_interfaces(self):
        """Test config file interface parsing."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\n[ens1f0]\n"
                "[ens2f0]\n")
            config_path = tmp_file.name
        try:
            monitor = PtpMonitor(
                'x', 30, 'y', init=False)
            monitor.ptp4l_config = config_path
            result = (
                monitor
                ._check_config_file_interfaces())
            self.assertEqual(
                result,
                ['ens1f0', 'ens2f0'])
        finally:
            os.unlink(config_path)

    def test_check_config_skip_special(self):
        """Test config skips special sections."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[global]\n"
                "[unicast_master_table]\n"
                "[ens3f0]\n")
            config_path = tmp_file.name
        try:
            monitor = PtpMonitor(
                'x', 30, 'y', init=False)
            monitor.ptp4l_config = config_path
            result = (
                monitor
                ._check_config_file_interfaces())
            self.assertEqual(
                result, ['ens3f0'])
        finally:
            os.unlink(config_path)

    def test_check_config_missing(self):
        """Test config with missing file."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor.ptp4l_config = (
            '/nonexistent.conf')
        result = (
            monitor
            ._check_config_file_interfaces())
        self.assertEqual(result, [])

    def test_set_ptp_devices(self):
        """Test set_ptp_devices."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor.ptp4l_config = (
            '/nonexistent.conf')
        monitor.set_ptp_devices()
        self.assertEqual(
            monitor.ptp_devices, [])

    def test_get_ptp_devices(self):
        """Test get_ptp_devices returns list."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor.ptp_devices = ['ptp0']
        self.assertEqual(
            monitor.get_ptp_devices(), ['ptp0'])

    def test_get_ptp_sync_source(self):
        """Test get_ptp_sync_source."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor.sync_source = (
            constants.ClockSourceType.TypePTP)
        self.assertEqual(
            monitor.get_ptp_sync_source(),
            constants.ClockSourceType.TypePTP)

    def test_set_clock_class_no_result(self):
        """Test clock class with no result."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._clock_class = None
        monitor._clock_class_retry = 0
        monitor.pmc_query_results = {}
        monitor.set_ptp_clock_class()
        self.assertEqual(
            monitor._clock_class, "248")

    def test_set_clock_class_with_result(self):
        """Test clock class with result."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._clock_class = None
        monitor._clock_class_retry = 3
        monitor.pmc_query_results = {
            'gm.ClockClass': '6'}
        monitor.set_ptp_clock_class()
        self.assertEqual(
            monitor._clock_class, '6')
        self.assertTrue(
            monitor._new_clock_class_event)

    def test_set_clock_class_same(self):
        """Test clock class unchanged."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._clock_class = '6'
        monitor._clock_class_retry = 3
        monitor.pmc_query_results = {
            'gm.ClockClass': '6'}
        monitor.set_ptp_clock_class()
        self.assertFalse(
            monitor._new_clock_class_event)

    def test_get_ptp_clock_class(self):
        """Test get_ptp_clock_class."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._clock_class = '7'
        monitor._clock_class_retry = 3
        monitor._clock_class_event_time = 123.0
        monitor.pmc_query_results = {
            'gm.ClockClass': '7'}
        new_event, clock_class, _ = (
            monitor.get_ptp_clock_class())
        self.assertEqual(clock_class, '7')

    def test_set_ptp_sync_state(self):
        """Test set_ptp_sync_state."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = (
            constants.UNKNOWN_PHC_STATE)
        monitor._ptp_event_time = 0
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.ptp4l_config = (
            '/nonexistent.conf')
        monitor.offset_threshold = 1000
        monitor.holdover_time = 30
        monitor.sync_source = (
            constants.ClockSourceType.TypeNA)
        with mock.patch(
                'trackingfunctionsdk.common'
                '.helpers.ptpsync'
                '.check_critical_resources',
                return_value=(
                    False, False,
                    False, False)):
            monitor.set_ptp_sync_state()
        self.assertEqual(
            monitor._ptp_sync_state,
            PtpState.Freerun)

    def test_get_ptp_sync_state(self):
        """Test get_ptp_sync_state."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._new_ptp_sync_event = True
        monitor._ptp_sync_state = (
            PtpState.Locked)
        monitor._ptp_event_time = 100.0
        event, state, event_time = (
            monitor.get_ptp_sync_state())
        self.assertTrue(event)
        self.assertEqual(
            state, PtpState.Locked)

    def test_ptp_status_missing_resources(self):
        """Test ptp_status missing resources."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = (
            PtpState.Freerun)
        monitor._ptp_event_time = 0
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.holdover_time = 30
        monitor.offset_threshold = 1000
        monitor.sync_source = (
            constants.ClockSourceType.TypeNA)
        with mock.patch(
                'trackingfunctionsdk.common'
                '.helpers.ptpsync'
                '.check_critical_resources',
                return_value=(
                    False, False,
                    False, False)):
            new_event, state, _ = (
                monitor.ptp_status())
        self.assertEqual(
            state, PtpState.Freerun)

    def test_ptp_status_locked_to_holdover(self):
        """Test locked to holdover transition."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        import time
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = (
            PtpState.Locked)
        monitor._ptp_event_time = time.time()
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.holdover_time = 30
        monitor.offset_threshold = 1000
        monitor.sync_source = (
            constants.ClockSourceType.TypeNA)
        with mock.patch(
                'trackingfunctionsdk.common'
                '.helpers.ptpsync'
                '.check_critical_resources',
                return_value=(
                    False, False,
                    False, False)):
            new_event, state, _ = (
                monitor.ptp_status())
        self.assertEqual(
            state, PtpState.Holdover)

    def test_ptp_status_holdover_to_freerun(self):
        """Test holdover to freerun transition."""
        from trackingfunctionsdk.common.helpers \
            .ptp_monitor import PtpMonitor
        monitor = PtpMonitor(
            'x', 30, 'y', init=False)
        monitor._ptp_sync_state = (
            PtpState.Holdover)
        monitor._ptp_event_time = 0
        monitor.phc2sys_service_name = 'y'
        monitor.ptp4l_service_name = 'x'
        monitor.holdover_time = 30
        monitor.offset_threshold = 1000
        monitor.sync_source = (
            constants.ClockSourceType.TypeNA)
        with mock.patch(
                'trackingfunctionsdk.common'
                '.helpers.ptpsync'
                '.check_critical_resources',
                return_value=(
                    False, False,
                    False, False)):
            new_event, state, _ = (
                monitor.ptp_status())
        self.assertEqual(
            state, PtpState.Freerun)


if __name__ == '__main__':
    unittest.main()
