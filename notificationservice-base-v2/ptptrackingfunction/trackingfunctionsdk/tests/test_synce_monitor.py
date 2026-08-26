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


class MockPinDirection(Enum):
    INPUT = "input"
    OUTPUT = "output"


mock_pynetlink.DeviceType = MockDeviceType
mock_pynetlink.PinDirection = MockPinDirection
mock_pynetlink.NetlinkDPLL = MagicMock
sys.modules['pynetlink'] = mock_pynetlink

from trackingfunctionsdk.common.helpers import synce_monitor  # noqa: E402
from trackingfunctionsdk.common.helpers.synce_monitor import (  # noqa: E402
    SynceMonitor, SynceState)

# synce_monitor binds LockStatus/DeviceType/PinDirection at import time.
# Under pytest, another test module (e.g. test_daemon) may import
# synce_monitor first with a plain-MagicMock pynetlink, leaving these
# symbols bound to the wrong mock. Rebind them to our enum mocks so these
# tests are independent of collection/import order.
synce_monitor.LockStatus = MockLockStatus
synce_monitor.DeviceType = MockDeviceType
synce_monitor.PinDirection = MockPinDirection


def _make_device(dev_type, lock_status, dev_clock_id=1):
    d = MagicMock()
    d.dev_type = dev_type
    d.lock_status = lock_status
    d.dev_clock_id = dev_clock_id
    return d


def _make_dir_pin(label, state, priority, direction=MockPinDirection.INPUT,
                  dev_type=MockDeviceType.EEC):
    p = MagicMock()
    p.pin_package_label = label
    p.pin_board_label = None
    p.pin_id = 0
    ps = MagicMock()
    ps.value = state
    p.pin_state = ps
    p.pin_priority = priority
    p.pin_direction = direction
    p.dev_type = dev_type
    return p


class TestSynceMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = SynceMonitor('synce_test', holdover_time=30)
        self.mock_dpll = MagicMock()
        self.monitor._dpll = self.mock_dpll
        self.monitor._clock_id = 1  # bypass config file parsing

    def test_locked_state(self):
        """DPLL locked → SynceState.Locked, new_event on first read."""
        self.mock_dpll.get_all_devices.return_value = [_make_device(
            MockDeviceType.EEC, MockLockStatus.LOCKED_AND_HOLDOVER)]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_no_event_when_unchanged(self):
        """Repeated locked reads → no new event after first."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertFalse(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_locked_to_holdover(self):
        """DPLL locked → holdover → state transitions correctly."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.HOLDOVER)
        ]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Holdover)

    def test_holdover_expires_to_freerun(self):
        """Holdover exceeding holdover_time → Freerun."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.HOLDOVER)
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
            _make_device(MockDeviceType.EEC, MockLockStatus.UNLOCKED)
        ]
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertTrue(new_event)
        self.assertEqual(state, SynceState.Freerun)

    def test_read_failure_no_state_change(self):
        """Read failure → state unchanged, no event."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.side_effect = Exception("netlink error")
        new_event, state, _ = self.monitor.get_synce_status()
        self.assertFalse(new_event)
        self.assertEqual(state, SynceState.Locked)

    def test_reconnect_after_failure(self):
        """After read failure, _dpll is set to None for reconnect."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.side_effect = Exception("err")
        self.monitor.get_synce_status()
        self.assertIsNone(self.monitor._dpll)

    def test_holdover_stays_in_holdover_within_time(self):
        """Holdover within holdover_time stays Holdover."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.HOLDOVER)
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
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        self.assertEqual(ql, 0x02)

    def test_clock_quality_freerun(self):
        """Freerun state reports QL-DNU (0x0f)."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.UNLOCKED)
        ]
        self.monitor.get_synce_status()
        new_event, ql, _ = self.monitor.get_clock_quality()
        self.assertTrue(new_event)
        self.assertEqual(ql, 0x0f)

    def test_clock_quality_no_event_unchanged(self):
        """No event when QL unchanged."""
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)
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


class MockPinState(Enum):
    CONNECTED = "connected"
    SELECTABLE = "selectable"
    DISCONNECTED = "disconnected"


class _PinList(list):
    """List of pins that supports filter_by_device_type(), mirroring the
    pynetlink DpllPins API the SUT calls after get_pins_by_clock_id()."""

    def filter_by_device_type(self, dev_type):
        return _PinList(p for p in self
                        if getattr(p, 'dev_type', MockDeviceType.EEC)
                        == dev_type)


def _make_pin(package_label, pin_state, priority, pin_id=1,
              dev_type=MockDeviceType.EEC):
    pin = MagicMock()
    pin.pin_package_label = package_label
    pin.pin_board_label = package_label
    pin.pin_id = pin_id
    pin.pin_state = pin_state
    pin.pin_priority = priority
    pin.dev_type = dev_type
    return pin


class TestSynceMonitorExtended(unittest.TestCase):
    """Tests for get_synce_status_extended."""

    def setUp(self):
        self.monitor = SynceMonitor('synce_test', holdover_time=30)
        self.mock_dpll = MagicMock()
        self.monitor._dpll = self.mock_dpll
        self.monitor._clock_id = 1  # bypass config file parsing

    def test_extended_returns_pin_states(self):
        """Extended response contains per-pin state dict."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
            _make_pin('RCLKA_REF1P', MockPinState.SELECTABLE, 10, pin_id=2),
            _make_pin('SMA1_REF3P', MockPinState.DISCONNECTED, 3, pin_id=3),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)

        new_event, info, _ = self.monitor.get_synce_status_extended()
        self.assertTrue(new_event)
        self.assertIn('pins', info)
        self.assertEqual(len(info['pins']), 3)
        self.assertEqual(info['pins']['GNSS_REF4P']['state'], 'connected')
        self.assertEqual(info['pins']['RCLKA_REF1P']['state'], 'selectable')
        self.assertEqual(info['pins']['SMA1_REF3P']['state'], 'disconnected')
        self.assertEqual(info['pins']['GNSS_REF4P']['priority'], 0)

    def test_extended_active_source_from_connected_pin(self):
        """active_source reports the connected pin's label."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
            _make_pin('RCLKA_REF1P', MockPinState.SELECTABLE, 10, pin_id=2),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)

        _, info, _ = self.monitor.get_synce_status_extended()
        self.assertEqual(info['active_source'], 'GNSS_REF4P')

    def test_extended_no_connected_pin_in_holdover(self):
        """During holdover, active_source is None."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.DISCONNECTED, 0, pin_id=1),
            _make_pin('RCLKA_REF1P', MockPinState.SELECTABLE, 10, pin_id=2),
        ]
        # First transition to locked, then to holdover. The poll loop calls
        # get_synce_status() before get_synce_status_extended() each cycle;
        # mirror that here so the cached aggregate state is populated.
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)
        self.monitor.get_synce_status()
        self.monitor.get_synce_status_extended()

        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.HOLDOVER)]
        self.monitor.get_synce_status()
        _, info, _ = self.monitor.get_synce_status_extended()
        self.assertIsNone(info['active_source'])

    def test_extended_reuses_cached_aggregate_state(self):
        """get_synce_status_extended() reuses the aggregate state cached by
        get_synce_status() and does not issue a second get_all_devices()
        netlink read (only get_pins_by_clock_id() for per-pin data)."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)

        # Poll loop order: aggregate first (one get_all_devices), then
        # extended.
        self.monitor.get_synce_status()
        self.assertEqual(self.mock_dpll.get_all_devices.call_count, 1)

        _, info, _ = self.monitor.get_synce_status_extended()

        # Extended must NOT have triggered another get_all_devices() read.
        self.assertEqual(self.mock_dpll.get_all_devices.call_count, 1)
        # It reuses the cached aggregate state.
        self.assertEqual(info['sync_state'], SynceState.Locked)
        self.assertEqual(info['dpll_state'], MockLockStatus.LOCKED.value)

    def test_extended_new_event_on_pin_state_change(self):
        """Pin state change fires new_event."""
        pins_locked = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = \
            _PinList(pins_locked)
        self.monitor.get_synce_status_extended()  # first event

        # Same DPLL state but pin disconnects
        pins_disc = [
            _make_pin('GNSS_REF4P', MockPinState.DISCONNECTED, 0, pin_id=1),
        ]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins_disc)
        new_event, info, _ = self.monitor.get_synce_status_extended()
        self.assertTrue(new_event)
        self.assertEqual(info['pins']['GNSS_REF4P']['state'], 'disconnected')

    def test_extended_no_event_when_unchanged(self):
        """No event when pin states unchanged."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)
        self.monitor.get_synce_status_extended()  # first
        new_event, _, _ = self.monitor.get_synce_status_extended()
        self.assertFalse(new_event)

    def test_extended_dpll_read_failure_preserves_last(self):
        """Failed pin read returns last known state, no event."""
        pins = [
            _make_pin('GNSS_REF4P', MockPinState.CONNECTED, 0, pin_id=1),
        ]
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(pins)
        self.monitor.get_synce_status_extended()  # populate

        # Simulate failure
        self.mock_dpll.get_pins_by_clock_id.side_effect = Exception("read err")
        new_event, info, _ = self.monitor.get_synce_status_extended()
        self.assertFalse(new_event)
        # Last known state preserved
        self.assertEqual(info['active_source'], 'GNSS_REF4P')

    def test_extended_label_fallback_chain(self):
        """Label falls back package_label -> board_label -> pin_<id>."""
        pin_board = _make_pin(None, MockPinState.SELECTABLE, 5, pin_id=2)
        pin_board.pin_board_label = 'BOARD_REF2P'
        pin_id_only = _make_pin(None, MockPinState.DISCONNECTED, 7, pin_id=9)
        pin_id_only.pin_board_label = None
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList([
            pin_board, pin_id_only])

        _, info, _ = self.monitor.get_synce_status_extended()
        self.assertIn('BOARD_REF2P', info['pins'])
        self.assertIn('pin_9', info['pins'])

    def test_extended_no_clock_id_returns_last(self):
        """No clock_id configured -> pin read returns None, no event."""
        self.monitor._clock_id = None
        self.mock_dpll.get_all_devices.return_value = [
            _make_device(MockDeviceType.EEC, MockLockStatus.LOCKED)]
        new_event, info, _ = self.monitor.get_synce_status_extended()
        self.assertFalse(new_event)
        # No prior extended state was populated
        self.assertIsNone(info)


class TestSyncePinFilter(unittest.TestCase):
    """Tests for _read_pin_states input-pin filtering and E810 safety."""

    def setUp(self):
        self.monitor = SynceMonitor('synce_test', holdover_time=30)
        self.mock_dpll = MagicMock()
        self.monitor._dpll = self.mock_dpll
        self.monitor._clock_id = 1

    def test_output_pins_excluded_and_active_source_is_input(self):
        """OUTPUT pins are dropped; active_source is the connected INPUT."""
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList([
            _make_dir_pin('REF4P', 'connected', 0, MockPinDirection.INPUT),
            _make_dir_pin('REF1P', 'selectable', 10, MockPinDirection.INPUT),
            _make_dir_pin('OUT7N', 'connected', None, MockPinDirection.OUTPUT),
            _make_dir_pin('OUT0P', 'connected', None, MockPinDirection.OUTPUT),
        ])
        pin_info, active_source = self.monitor._read_pin_states()
        self.assertIn('REF4P', pin_info)
        self.assertIn('REF1P', pin_info)
        self.assertNotIn('OUT7N', pin_info)
        self.assertNotIn('OUT0P', pin_info)
        self.assertEqual(active_source, 'REF4P')

    def test_out_label_fallback_when_no_direction(self):
        """E810-safe: no pin_direction attr → exclude OUT* by label."""
        ref = _make_dir_pin('REF4P', 'connected', 0)
        ref.pin_direction = None
        out = _make_dir_pin('OUT7N', 'connected', None)
        out.pin_direction = None
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList([ref, out])
        pin_info, active_source = self.monitor._read_pin_states()
        self.assertIn('REF4P', pin_info)
        self.assertNotIn('OUT7N', pin_info)
        self.assertEqual(active_source, 'REF4P')

    def test_no_dpll_returns_none_safely(self):
        """E810/no-EEC host: _get_dpll None -> (None, None), no crash."""
        # Force the no-DPLL path deterministically (NetlinkDPLL is a mock
        # in the test env, so _get_dpll would otherwise return a truthy
        # MagicMock).
        with patch.object(self.monitor, '_get_dpll', return_value=None):
            pin_info, active_source = self.monitor._read_pin_states()
        self.assertIsNone(pin_info)
        self.assertIsNone(active_source)

    def test_extended_new_event_on_input_priority_change(self):
        """An INPUT pin priority change fires new_event (push trigger)."""
        self.mock_dpll.get_all_devices.return_value = [_make_device(
            MockDeviceType.EEC, MockLockStatus.LOCKED)]
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList([
            _make_dir_pin('REF4P', 'connected', 0, MockPinDirection.INPUT)])
        ev1, _, _ = self.monitor.get_synce_status_extended()
        self.assertTrue(ev1)  # first read is always an event
        # unchanged → no event
        ev2, _, _ = self.monitor.get_synce_status_extended()
        self.assertFalse(ev2)
        # change priority → event
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList([
            _make_dir_pin('REF4P', 'connected', 14, MockPinDirection.INPUT)])
        ev3, info3, _ = self.monitor.get_synce_status_extended()
        self.assertTrue(ev3)
        self.assertEqual(info3['pins']['REF4P']['priority'], 14)

    def test_pps_pins_excluded_on_shared_clock_id(self):
        """GNR-D shared clock_id: EEC+PPS copies of a pin -> only EEC kept.

        On the zl3073x a single clock_id exposes both the EEC and PPS
        device; get_pins_by_clock_id() returns a copy of each pin per parent
        engine (verified on sx-047: pin 7 GNSS_1PPS_IN under dev=0/EEC and
        dev=1/PPS). _read_pin_states() must scope to EEC so the PPS copy does
        not overwrite the EEC copy in pin_info and active_source stays
        deterministic.
        """
        eec_gnss = _make_dir_pin('GNSS_1PPS_IN', 'connected', 0,
                                 MockPinDirection.INPUT,
                                 dev_type=MockDeviceType.EEC)
        pps_gnss = _make_dir_pin('GNSS_1PPS_IN', 'disconnected', 0,
                                 MockPinDirection.INPUT,
                                 dev_type=MockDeviceType.PPS)
        pps_sdp = _make_dir_pin('ETH01_SDP_TIMESYNC_0', 'connected', 1,
                                MockPinDirection.INPUT,
                                dev_type=MockDeviceType.PPS)
        self.mock_dpll.get_pins_by_clock_id.return_value = _PinList(
            [eec_gnss, pps_gnss, pps_sdp])

        pin_info, active_source = self.monitor._read_pin_states()

        # Only the EEC-parented GNSS pin survives; PPS copies are dropped.
        self.assertEqual(active_source, 'GNSS_1PPS_IN')
        self.assertEqual(pin_info['GNSS_1PPS_IN']['state'], 'connected')
        self.assertNotIn('ETH01_SDP_TIMESYNC_0', pin_info)
        self.assertEqual(len(pin_info), 1)


if __name__ == '__main__':
    unittest.main()
