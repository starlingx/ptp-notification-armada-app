#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import sys
import unittest
from unittest.mock import MagicMock
from enum import Enum

# Mock pynetlink before any imports that reference it
mock_pynetlink = MagicMock()


class MockLockStatus(Enum):
    LOCKED = "locked"
    LOCKED_AND_HOLDOVER = "locked-ho-acq"
    HOLDOVER = "holdover"
    UNLOCKED = "unlocked"


class MockDeviceType(Enum):
    EEC = "eec"
    PPS = "pps"


mock_pynetlink.LockStatus = MockLockStatus
mock_pynetlink.DeviceType = MockDeviceType
mock_pynetlink.NetlinkDPLL = MagicMock
sys.modules['pynetlink'] = mock_pynetlink

from trackingfunctionsdk.common.helpers.synce_monitor import (  # noqa: E402
    SynceMonitor, SynceState)
from trackingfunctionsdk.common.helpers import synce_monitor as _sm  # noqa: E402

# Use the DeviceType/LockStatus that synce_monitor.py actually bound at import
_DeviceType = _sm.DeviceType
_LockStatus = _sm.LockStatus


TEST_CLOCK_ID = 12345678


def _make_device(dev_type, lock_status, clock_id=TEST_CLOCK_ID):
    d = MagicMock()
    d.dev_type = dev_type
    d.lock_status = lock_status
    d.dev_clock_id = clock_id
    return d


class TestSynceMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = SynceMonitor('synce_test', holdover_time=30)
        self.monitor._clock_id = TEST_CLOCK_ID
        self.mock_dpll = MagicMock()
        self.monitor._dpll = self.mock_dpll

    def test_locked_state(self):
        """DPLL locked → SynceState.Locked, new_event on first read."""
        self.mock_dpll.get_all_devices.return_value = [_make_device(
            _DeviceType.EEC, _LockStatus.LOCKED_AND_HOLDOVER)]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_no_event_when_unchanged(self):
        """Repeated locked reads → no new event after first."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertFalse(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_locked_to_holdover(self):
        """DPLL locked → holdover → state transitions correctly."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.HOLDOVER)
        ]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Holdover)

    def test_holdover_expires_to_freerun(self):
        """Holdover exceeding holdover_time → Freerun."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.HOLDOVER)
        ]
        self.monitor.get_synce_status()

        # Simulate time beyond holdover
        self.monitor._holdover_start -= 31

        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Freerun)

    def test_unlocked_is_freerun(self):
        """DPLL unlocked → Freerun."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.UNLOCKED)
        ]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Freerun)

    def test_read_failure_no_state_change(self):
        """Read failure → state unchanged, no event."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.side_effect = Exception("netlink error")
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertFalse(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_reconnect_after_failure(self):
        """After read failure, _dpll is set to None for reconnect."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.side_effect = Exception("err")
        self.monitor.get_synce_status()
        self.assertIsNone(self.monitor._dpll)

    def test_holdover_stays_in_holdover_within_time(self):
        """Holdover within holdover_time stays Holdover."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.HOLDOVER)
        ]
        self.monitor.get_synce_status()

        # Still within holdover_time
        self.monitor._holdover_start -= 10  # only 10s

        new_event, state, _ = self.monitor.get_synce_status()
        self.assertFalse(new_event)
        self.assertEqual(state, SynceState.Holdover)

    def test_clock_quality_locked(self):
        """Locked state reports QL-PRC (0x02)."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        self.assertEqual(ql, 0x02)

    def test_clock_quality_freerun(self):
        """Freerun state reports QL-DNU (0x0f)."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.UNLOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        self.assertEqual(ql, 0x0f)

    def test_clock_quality_no_event_unchanged(self):
        """No event when QL unchanged."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(_DeviceType.EEC, _LockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()
        self.monitor.get_clock_quality()  # first
        new_event, _, _ = self.monitor.get_clock_quality()
        self.assertFalse(new_event)


if __name__ == '__main__':
    unittest.main()
