#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import sys
import struct
import unittest
from unittest.mock import MagicMock, patch
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


def _ql_response(dev, ql):
    """Build a synce4l TLV response echoing DEV_NAME + GET_QL(ql)."""
    d = dev.encode()
    return (struct.pack('<HH', 1, len(d)) + d
            + struct.pack('<HH', 4, 1) + bytes([ql])
            + struct.pack('<HH', 8, 0))


class TestSynceClockQualitySocket(unittest.TestCase):
    """clock-quality sourced from the synce4l management socket."""

    def setUp(self):
        self.monitor = SynceMonitor('synce_test', holdover_time=30)
        self.monitor._clock_id = 1
        self.monitor._socket_path = '/run/fake_synce4l_socket'
        # Fallback mapping values (used only when the socket fails).
        self.monitor._sync_state = SynceState.Locked
        self.monitor._locked_ql = 0x02

    def test_parse_ql_response(self):
        """GET_QL uint8 is extracted from a TLV response."""
        self.assertEqual(
            SynceMonitor._parse_ql_response(_ql_response('synce_test', 0x01)),
            0x01)

    def test_parse_ql_response_error_tlv(self):
        """An error TLV yields None (caller falls back)."""
        err = struct.pack('<HH', 3, 4) + b'oops' + struct.pack('<HH', 8, 0)
        self.assertIsNone(SynceMonitor._parse_ql_response(err))

    def test_clock_quality_uses_socket_ql(self):
        """When the socket returns a QL it is reported, not the mapping."""
        with patch('socket.socket') as mock_sock_cls:
            sock = mock_sock_cls.return_value
            sock.recv.return_value = _ql_response('synce_test', 0x04)
            new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        # 0x04 came from the socket; the Locked-state mapping is 0x02.
        self.assertEqual(ql, 0x04)

    def test_clock_quality_falls_back_on_socket_error(self):
        """Socket failure falls back to the state-derived QL mapping."""
        with patch('socket.socket') as mock_sock_cls:
            sock = mock_sock_cls.return_value
            sock.connect.side_effect = OSError("no socket")
            new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        self.assertEqual(ql, 0x02)  # Locked-state fallback

    def test_query_returns_none_when_no_socket_path(self):
        """No configured socket path -> query returns None."""
        self.monitor._socket_path = None
        self.assertIsNone(self.monitor._query_synce4l_ql())


if __name__ == '__main__':
    unittest.main()
