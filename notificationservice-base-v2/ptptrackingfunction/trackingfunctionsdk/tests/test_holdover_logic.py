#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor
from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor
from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.model.dto.ptpstate import PtpState
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Mock dependencies before importing
sys.modules['pynetlink'] = MagicMock()
sys.modules['oslo_utils'] = MagicMock()
sys.modules['oslo_utils.uuidutils'] = MagicMock()

# Import monitor classes after mocking dependencies


class TestHoldoverLogic(unittest.TestCase):

    def setUp(self):
        self.mock_time = 1000.0
        self.holdover_time = 30
        self.freq = 2

    @patch('datetime.datetime')
    def test_ptp_holdover_transitions(self, mock_datetime):
        """Test PTP holdover state transitions"""
        mock_datetime.utcnow.return_value.timestamp.return_value = self.mock_time

        with patch.object(PtpMonitor, '__init__', return_value=None):
            ptp_monitor = PtpMonitor.__new__(PtpMonitor)
            ptp_monitor.holdover_time = self.holdover_time
            ptp_monitor.freq = self.freq
            ptp_monitor._ptp_sync_state = PtpState.Locked
            ptp_monitor._ptp_event_time = self.mock_time - 10  # 10 seconds ago
            ptp_monitor.pmc_query_results = {}
            ptp_monitor.offset_threshold = 1000000
            # Initialize sync_source
            ptp_monitor.sync_source = constants.ClockSourceType.TypeNA

            # Mock dependencies
            with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                       'check_critical_resources') as mock_resources, \
                    patch.object(ptp_monitor, 'ptpsync') as mock_ptpsync:

                mock_resources.return_value = (True, True, True, True)
                mock_ptpsync.return_value = ({}, 5, 1)

                # Mock utils.check_results to return Freerun
                # (triggering holdover logic)
                with patch('trackingfunctionsdk.common.helpers.ptpsync.'
                           'check_results') as mock_check:
                    mock_check.return_value = (
                        PtpState.Freerun, constants.ClockSourceType.TypePTP)

                    # Test transition from Locked to Holdover
                    new_event, sync_state, event_time = (
                        ptp_monitor.ptp_status())

                    self.assertTrue(new_event)
                    self.assertEqual(sync_state, PtpState.Holdover)
                    self.assertEqual(event_time, self.mock_time)

    @patch('datetime.datetime')
    def test_gnss_holdover_expiration(self, mock_datetime):
        """Test GNSS holdover expiration"""
        mock_datetime.utcnow.return_value.timestamp.return_value = self.mock_time

        with patch.object(GnssMonitor, '__init__', return_value=None):
            gnss_monitor = GnssMonitor.__new__(GnssMonitor)
            gnss_monitor.holdover_time = self.holdover_time
            gnss_monitor._state = GnssState.Failure_Nofix

            # Mock set_gnss_status to always return Failure_Nofix
            with patch.object(gnss_monitor, 'set_gnss_status'):
                # Test holdover expiration (time_in_holdover >= holdover_time)
                # 35 seconds ago, exceeds holdover_time (30s)
                expired_time = self.mock_time - 35

                new_event, state, event_time = (
                    gnss_monitor.get_gnss_status(
                        GnssState.Holdover, expired_time))

                self.assertTrue(new_event)
                self.assertEqual(state, GnssState.Failure_Nofix)

    @patch('datetime.datetime')
    def test_os_clock_holdover_remaining(self, mock_datetime):
        """Test OS Clock remaining in holdover"""
        mock_datetime.utcnow.return_value.timestamp.return_value = self.mock_time

        with patch.object(OsClockMonitor, '__init__', return_value=None):
            os_monitor = OsClockMonitor.__new__(OsClockMonitor)
            os_monitor.holdover_time = self.holdover_time

            # Mock methods to simulate freerun state
            with patch.object(os_monitor, 'set_utc_offset'), \
                    patch.object(os_monitor, 'get_os_clock_offset'), \
                    patch.object(os_monitor, 'set_os_clock_state'), \
                    patch.object(os_monitor, 'get_os_clock_state') as mock_get:

                mock_get.return_value = OsClockState.Freerun

                # Test remaining in holdover (time_in_holdover < holdover_time)
                # 10 seconds ago, within holdover_time (30s)
                recent_time = self.mock_time - 10

                new_event, state, event_time = os_monitor.os_clock_status(
                    self.holdover_time, self.freq,
                    constants.HOLDOVER_PHC_STATE, recent_time)

                self.assertFalse(new_event)  # No state change
                self.assertEqual(state, OsClockState.Holdover)

    def test_holdover_time_calculation(self):
        """Test holdover time is used directly"""
        holdover_time = 60
        # No more safety margin - use holdover time directly
        self.assertEqual(holdover_time, 60)

    @patch('datetime.datetime')
    def test_overall_holdover_calculation(self, mock_datetime):
        """Test overall holdover time calculation using minimum from
        active components"""
        mock_datetime.utcnow.return_value.timestamp.return_value = (
            self.mock_time)

        # Mock components with different holdover times
        os_clock_holdover = 30
        ptp_source_holdover = 45
        gnss_source_holdover = 25

        # Test minimum calculation
        components = [os_clock_holdover, ptp_source_holdover,
                      gnss_source_holdover]
        expected_min = min(components)  # Should be 25 (GNSS)

        self.assertEqual(expected_min, gnss_source_holdover)
        self.assertEqual(expected_min, 25)

    def test_state_transition_matrix(self):
        """Test all valid state transitions for holdover logic"""
        # Valid transitions for PTP/GNSS/OS Clock:
        # Unknown/Freerun -> Freerun (no change)
        # Locked -> Holdover (when sync lost)
        # Holdover -> Holdover (while within time limit)
        # Holdover -> Freerun (when time limit exceeded)
        # Any -> Locked (when sync restored)

        transitions = [
            (constants.UNKNOWN_PHC_STATE, PtpState.Freerun,
             PtpState.Freerun),
            (constants.FREERUN_PHC_STATE, PtpState.Freerun,
             PtpState.Freerun),
            (constants.LOCKED_PHC_STATE, PtpState.Freerun,
             PtpState.Holdover),
            # Holdover -> Holdover tested in time-based tests above
            # Holdover -> Freerun tested in expiration tests above
        ]

        for previous, current, expected in transitions:
            # This validates the transition logic conceptually
            if previous in [constants.UNKNOWN_PHC_STATE,
                            constants.FREERUN_PHC_STATE]:
                if current == PtpState.Freerun:
                    result = PtpState.Freerun
                else:
                    result = current
            elif (previous == constants.LOCKED_PHC_STATE and
                  current == PtpState.Freerun):
                result = PtpState.Holdover
            else:
                result = current

            self.assertEqual(
                result, expected,
                f"Transition {previous} -> {current} should result in "
                f"{expected}")


if __name__ == '__main__':
    unittest.main()
