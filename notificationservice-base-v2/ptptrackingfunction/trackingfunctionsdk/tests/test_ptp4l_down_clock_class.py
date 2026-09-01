# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""Tests for PTP behaviour when the ptp4l service is down.

When a monitored ptp4l instance's service is stopped, the notification
service can no longer poll it via pmc. The clock class must degrade to 248
(free-run) instead of continuing to report the stale locked value, and the
sync state must report Freerun directly rather than a (false) holdover,
so that state and clockClass stay consistent.
"""

from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.ptpstate import PtpState
import sys
import unittest
from unittest.mock import patch, MagicMock

# Mock dependencies before importing the monitor classes
sys.modules['pynetlink'] = MagicMock()
sys.modules['oslo_utils'] = MagicMock()
sys.modules['oslo_utils.uuidutils'] = MagicMock()


class TestPtp4lDownClockClass(unittest.TestCase):

    def setUp(self):
        self.mock_time = 1000.0
        self.holdover_time = 30

    def _make_monitor(self, previous_sync_state):
        """Build a PtpMonitor instance without running __init__."""
        ptp_monitor = PtpMonitor.__new__(PtpMonitor)
        ptp_monitor.holdover_time = self.holdover_time
        ptp_monitor._ptp_sync_state = previous_sync_state
        ptp_monitor._ptp_event_time = self.mock_time - 10  # 10s ago
        ptp_monitor.offset_threshold = 1000000
        ptp_monitor.sync_source = constants.ClockSourceType.TypeNA
        # Stale results left over from the last successful poll while locked
        ptp_monitor.pmc_query_results = {
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE6}
        ptp_monitor._clock_class = constants.CLOCK_CLASS_VALUE6
        ptp_monitor._clock_class_retry = 3
        ptp_monitor._new_clock_class_event = False
        ptp_monitor._clock_class_event_time = self.mock_time
        return ptp_monitor

    @patch('datetime.datetime')
    def test_ptp4l_down_reports_freerun_not_holdover(self, mock_datetime):
        """ptp4l down: previously Locked stays Freerun (no false holdover)."""
        mock_datetime.utcnow.return_value.timestamp.return_value = \
            self.mock_time

        with patch.object(PtpMonitor, '__init__', return_value=None):
            ptp_monitor = self._make_monitor(PtpState.Locked)

            with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                       'check_critical_resources') as mock_resources, \
                    patch.object(ptp_monitor, 'ptpsync') as mock_ptpsync:
                # ptp4l (2nd value) is down; pmc/ptp4lconf present
                mock_resources.return_value = (True, False, False, True)

                new_event, sync_state, _ = ptp_monitor.ptp_status()

                # pmc must not have been polled
                mock_ptpsync.assert_not_called()
                self.assertTrue(new_event)
                self.assertEqual(sync_state, PtpState.Freerun)
                # Stale pmc results must be cleared and retry bypassed
                self.assertEqual(ptp_monitor.pmc_query_results, {})
                self.assertEqual(ptp_monitor._clock_class_retry, 0)

    @patch('datetime.datetime')
    def test_ptp4l_down_degrades_clock_class_to_248(self, mock_datetime):
        """ptp4l down: clockClass degrades to 248 immediately (no retry)."""
        mock_datetime.utcnow.return_value.timestamp.return_value = \
            self.mock_time

        with patch.object(PtpMonitor, '__init__', return_value=None):
            ptp_monitor = self._make_monitor(PtpState.Locked)

            with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                       'check_critical_resources') as mock_resources, \
                    patch.object(ptp_monitor, 'ptpsync'):
                mock_resources.return_value = (True, False, False, True)

                # ptp_status() clears the stale cache and zeroes the retry
                ptp_monitor.ptp_status()

                # get_ptp_clock_class() runs next in the same publish cycle
                new_clock_class_event, clock_class, _ = \
                    ptp_monitor.get_ptp_clock_class()

                self.assertTrue(new_clock_class_event)
                self.assertEqual(clock_class, constants.CLOCK_CLASS_VALUE248)
                # retry counter is reset after degrading
                self.assertEqual(ptp_monitor._clock_class_retry, 3)

    @patch('datetime.datetime')
    def test_reference_lost_with_ptp4l_running_still_holdover(
            self, mock_datetime):
        """ptp4l up, reference lost: Locked -> Holdover is unchanged."""
        mock_datetime.utcnow.return_value.timestamp.return_value = \
            self.mock_time

        with patch.object(PtpMonitor, '__init__', return_value=None):
            ptp_monitor = self._make_monitor(PtpState.Locked)

            with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                       'check_critical_resources') as mock_resources, \
                    patch.object(ptp_monitor, 'ptpsync') as mock_ptpsync, \
                    patch('trackingfunctionsdk.common.helpers.ptpsync.'
                          'check_results') as mock_check:
                # All resources present (healthy poll path)
                mock_resources.return_value = (True, True, True, True)
                mock_ptpsync.return_value = ({}, 5, 1)
                # Reference lost -> check_results reports Freerun
                mock_check.return_value = (
                    PtpState.Freerun, constants.ClockSourceType.TypePTP)

                new_event, sync_state, _ = ptp_monitor.ptp_status()

                # holdover machine still promotes Locked -> Holdover
                self.assertTrue(new_event)
                self.assertEqual(sync_state, PtpState.Holdover)

    @patch('datetime.datetime')
    def test_ptp4l_down_from_freerun_stays_freerun(self, mock_datetime):
        """ptp4l down: previously Freerun remains Freerun."""
        mock_datetime.utcnow.return_value.timestamp.return_value = \
            self.mock_time

        with patch.object(PtpMonitor, '__init__', return_value=None):
            ptp_monitor = self._make_monitor(PtpState.Freerun)

            with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                       'check_critical_resources') as mock_resources, \
                    patch.object(ptp_monitor, 'ptpsync'):
                mock_resources.return_value = (True, False, False, True)

                _, sync_state, _ = ptp_monitor.ptp_status()

                self.assertEqual(sync_state, PtpState.Freerun)


if __name__ == '__main__':
    unittest.main()
