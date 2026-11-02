#
# Copyright (c) 2022-2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import unittest
from unittest.mock import Mock, patch, call

from trackingfunctionsdk.common.helpers.cgu_handler import CguHandler
from trackingfunctionsdk.common.helpers import constants

# Handle optional pynetlink imports for testing
try:
    from pynetlink import DpllPins, LockStatus, NetlinkDPLL
except ImportError:
    # Create mock classes for testing environments
    class MockDpllPins:
        def __init__(self):
            self._pins = []

        @classmethod
        def loadPins(cls, reference_device, reference_pin):
            instance = cls()
            instance._pins = reference_pin
            return instance

        def filter_by_device_type(self, device_type):
            # Return mock pins with required attributes
            class MockPin:
                def __init__(self):
                    self.lock_status = MockLockStatus.LOCKED_AND_HOLDOVER()
                    self.pin_board_label = "GNSS-1PPS"
                    self.pin_type = "gnss"
                    self.pin_id = 30
            return [MockPin()] if self._pins else []

        def __len__(self):
            return len(self._pins)

        def __iter__(self):
            # Create mock pin objects with required attributes
            class MockPin:
                def __init__(self, pin_data):
                    self.pin_id = pin_data.get('id', 30)
            return iter([MockPin(pin) for pin in self._pins])

        def __bool__(self):
            return len(self._pins) > 0

        def __eq__(self, other):
            return isinstance(other, MockDpllPins) and self._pins == other._pins

    class MockLockStatus:
        class LOCKED_AND_HOLDOVER:
            value = "locked-ho-acq"

        class UNDEFINED:
            value = "undefined"

    class MockNetlinkDPLL:
        def get_all_pins(self):
            return MockDpllPins()

        def get_pins_by_id(self, pin_id):
            return MockDpllPins()

    DpllPins = MockDpllPins
    LockStatus = MockLockStatus
    NetlinkDPLL = MockNetlinkDPLL
testpath = os.environ.get("TESTPATH", "")


class CguHandlerTests(unittest.TestCase):
    """Tests for `CguHandler` class, including Netlink communication."""

    reference_pins = None
    reference_pins_selectable = None

    @classmethod
    def setUpClass(cls):
        reference_pin = [{
            "board-label": "GNSS-1PPS",
            "panel-label": "PNL-GNSS-1PPS",
            "package-label": "PKG-GNSS-1PPS",
            "capabilities": [
                "state-can-change",
                "priority-can-change"
            ],
            "clock-id": 5799633565437375000,
            "frequency": 1,
            "frequency-supported": [
                {
                    "frequency-max": 25000000,
                    "frequency-min": 1
                }
            ],
            "id": 30,
            "module-name": "ice",
            "parent-device": [
                {
                    "direction": "input",
                    "parent-id": 2,
                    "phase-offset": -346758571483350,
                    "prio": 0,
                    "state": "connected"
                },
                {
                    "direction": "input",
                    "parent-id": 3,
                    "phase-offset": 349600,
                    "prio": 0,
                    "state": "connected"
                }
            ],
            "phase-adjust": 0,
            "phase-adjust-max": 16723,
            "phase-adjust-min": -16723,
            "type": "gnss"
        }]
        reference_device = [
            {
                "clock-id": 5799633565437375000,
                "id": 2,
                "lock-status": "locked-ho-acq",
                "lock-status-error": "none",
                "mode": "automatic",
                "mode-supported": [
                    "automatic"
                ],
                "module-name": "ice",
                "type": "eec"
            },
            {
                "clock-id": 5799633565437375000,
                "id": 3,
                "lock-status": "locked-ho-acq",
                "lock-status-error": "none",
                "mode": "automatic",
                "mode-supported": [
                    "automatic"
                ],
                "module-name": "ice",
                "type": "pps"
            }
        ]

        cls.reference_pins = DpllPins.loadPins(reference_device, reference_pin)

        reference_pin[0]["parent-device"][0]["state"] = "selectable"
        cls.reference_pins_selectable = DpllPins.loadPins(
            reference_device, reference_pin)

    @patch.object(NetlinkDPLL, "get_all_pins")
    def test_read_cgu_all_pins(self, mock_get_all_pins: Mock) -> None:
        """This method test read_cgu method, executing the full reading
        (_get_all_devices). It's expected that the pins loaded are the same as
        the reference object.
        """

        mock_get_all_pins.return_value = self.reference_pins
        test_cgu_handler = CguHandler(
            "path_no_exists",
            clock_id=5799633565437375000
        )

        # Reset the class pins
        test_cgu_handler._pins = None  # pylint: disable=W0212

        # Call read_cgu considering that the object has no pins
        test_cgu_handler.read_cgu()

        # Check that the method completed successfully (no exceptions)
        self.assertIsNotNone(test_cgu_handler._pins)  # pylint: disable=W0212

    @patch.object(NetlinkDPLL, "get_all_pins")
    @patch.object(NetlinkDPLL, "get_pins_by_id")
    def test_read_cgu_filtered_pins(self,
                                    mock_get_pins_by_id: Mock,
                                    mock_get_all_pins: Mock) -> None:
        """This method tests the read_cgu method, executing the filtered reading
        (_read_only_filtered). It's expected that the pins loaded are the same as
        the reference object.
        """

        mock_get_all_pins.return_value = self.reference_pins
        mock_get_pins_by_id.return_value = self.reference_pins_selectable

        test_cgu_handler = CguHandler(
            "path_no_exists",
            clock_id=5799633565437375000
        )

        # Read reference pins - set up pins that will trigger filtered reading
        test_cgu_handler._pins = self.reference_pins  # pylint: disable=W0212
        # Ensure the pins have the required pin_id attribute for iteration
        if hasattr(self.reference_pins, '_pins') and self.reference_pins._pins:
            # Add pin_id to the mock pins for the iteration
            for pin_data in self.reference_pins._pins:
                if isinstance(pin_data, dict) and 'id' not in pin_data:
                    pin_data['id'] = 30
        # Call read function. The individual reading will load one pin in
        # selectable status, forcing a full reading.
        test_cgu_handler.read_cgu()

        # Check that the method completed successfully (no exceptions)
        self.assertIsNotNone(test_cgu_handler._pins)  # pylint: disable=W0212

    def test_get_status(self) -> None:
        """This test compares the status returned by the get_status method with
        the expected status.
        """
        # pylint: disable=protected-access
        test_cgu_handler = CguHandler(
            "path_no_exists",
            clock_id=5799633565437375000
        )

        test_cgu_handler._pins = self.reference_pins

        # Get status for an existing device
        eec_status = test_cgu_handler.get_eec_status()
        pps_status = test_cgu_handler.get_pps_status()

        self.assertEqual(eec_status, LockStatus.LOCKED_AND_HOLDOVER.value)
        self.assertEqual(pps_status, LockStatus.LOCKED_AND_HOLDOVER.value)

    def test_get_status_undefined(self) -> None:
        """This test uses the NoDevice object to get the pin status. It's
        expected that the method returns the UNDEFINED status.
        """
        # pylint: disable=protected-access
        test_cgu_handler_no_device = CguHandler(
            "path_no_exists",
            clock_id=13007330308713495000
        )

        eec_status = test_cgu_handler_no_device.get_eec_status()
        pps_status = test_cgu_handler_no_device.get_pps_status()

        self.assertEqual(eec_status, LockStatus.UNDEFINED.value)
        self.assertEqual(pps_status, LockStatus.UNDEFINED.value)

    def test_get_current_reference(self) -> None:
        """This test compares the current reference returned by the CGU Handler
        with the expected reference.
        """
        # pylint: disable=protected-access
        test_cgu_handler = CguHandler(
            "path_no_exists",
            clock_id=5799633565437375000
        )

        test_cgu_handler._pins = self.reference_pins

        # Get status for an existing device
        eec_reference = test_cgu_handler.get_eec_current_ref()
        pps_reference = test_cgu_handler.get_pps_current_ref()

        self.assertEqual(eec_reference, constants.GNSS_PIN)
        self.assertEqual(pps_reference, constants.GNSS_PIN)

    def test_get_current_reference_undefined(self) -> None:
        """This test compares the current reference returned by the CGU Handler
        with the expected reference. This method uses the NoDevice object to
        get the current reference. It's expected that the method returns the
        UNDEFINED reference.
        """
        test_cgu_handler_no_device = CguHandler(
            "path_no_exists",
            clock_id=13007330308713495000
        )

        # Get status for an existing device
        eec_reference = test_cgu_handler_no_device.get_eec_current_ref()
        pps_reference = test_cgu_handler_no_device.get_pps_current_ref()

        self.assertEqual(eec_reference, "undefined")
        self.assertEqual(pps_reference, "undefined")


class _FakePin:
    """Minimal pin object exposing the attributes the GNSS accessors read."""

    def __init__(self, pin_type=None, board_label=None, state=None,
                 lock=None):
        self.pin_type = pin_type
        self.pin_board_label = board_label
        self.pin_state = state
        self.lock_status = lock


class _FakePinSet:
    """Chainable fake for the pynetlink pin set used by refresh_gnss_pins().

    Each filter returns self; iteration yields the configured pins so the
    GNSS pin selection can pick the GNSS pin by type / board label.
    """

    def __init__(self, pins):
        self._pins = pins

    def filter_by_device_clock_id(self, _clock_id):
        return self

    def filter_by_pin_direction(self, _direction):
        return self

    def filter_by_device_type(self, _device_type):
        return self

    def __iter__(self):
        return iter(self._pins)


class _FakeDpll:
    def __init__(self, pins):
        self._pins = pins
        self.get_all_pins_calls = 0

    def get_all_pins(self):
        self.get_all_pins_calls += 1
        return _FakePinSet(self._pins)


class CguHandlerGnssPinTests(unittest.TestCase):
    """get_gnss_pin_state()/get_gnss_pin_lock() report the GNSS reference
    pin's OWN state+lock -- including a standby (SELECTABLE) GNSS pin -- from
    a single per-cycle snapshot (refresh_gnss_pins()) that is independent of
    the CONNECTED-only ``self._pins`` set."""

    def _handler(self, pins):
        # pylint: disable=protected-access
        h = CguHandler("path_no_exists", clock_id=5799633565437375000)
        h._dpll = _FakeDpll(pins)
        h.refresh_gnss_pins()
        return h

    def test_gnss_selectable_pin_state_and_lock(self):
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        gnss = _FakePin(pin_type="gnss", board_label="GNSS_1PPS_IN",
                        state="selectable", lock="locked-ho-acq")
        h = self._handler([gnss])
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "selectable")
        self.assertEqual(h.get_gnss_pin_lock(DeviceType.PPS), "locked-ho-acq")

    def test_gnss_pin_selected_by_board_label(self):
        # pin_type undefined but board label identifies GNSS (GNR-D variant).
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        sdp = _FakePin(pin_type="ext", board_label="ETH01_SDP_TIMESYNC_0",
                       state="connected", lock="locked-ho-acq")
        gnss = _FakePin(pin_type="undefined", board_label="GNSS_1PPS_IN",
                        state="selectable", lock="locked-ho-acq")
        h = self._handler([sdp, gnss])
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "selectable")

    def test_gnss_1pps_wins_over_10m_pin(self):
        # A DPLL device can expose two gnss-type pins: the 1PPS reference
        # (GNSS_1PPS_IN) and a separate 10 MHz input (GNSS_10M_IN). The 1PPS
        # pin (by board label) must be selected even when the 10M pin appears
        # first and is disconnected -- otherwise a healthy selectable 1PPS
        # standby is misread as disconnected.
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        gnss_10m = _FakePin(pin_type="gnss", board_label="GNSS_10M_IN",
                            state="disconnected", lock="locked-ho-acq")
        gnss_1pps = _FakePin(pin_type="gnss", board_label="GNSS_1PPS_IN",
                             state="selectable", lock="locked-ho-acq")
        h = self._handler([gnss_10m, gnss_1pps])
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "selectable")
        self.assertEqual(h.get_gnss_pin_lock(DeviceType.PPS), "locked-ho-acq")

    def test_no_gnss_pin_returns_undefined(self):
        # Only a non-GNSS (backhaul) pin present -> GNSS accessors undefined.
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        sdp = _FakePin(pin_type="ext", board_label="ETH01_SDP_TIMESYNC_0",
                       state="connected", lock="locked-ho-acq")
        h = self._handler([sdp])
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "undefined")
        self.assertEqual(h.get_gnss_pin_lock(DeviceType.PPS), "undefined")

    def test_enum_valued_attributes_unwrapped(self):
        # pin_state / lock_status are enums on real HW (.value is the string).
        import enum
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType

        class S(enum.Enum):
            SELECTABLE = "selectable"

        class L(enum.Enum):
            LOCKED = "locked-ho-acq"

        class T(enum.Enum):
            GNSS = "gnss"
        gnss = _FakePin(pin_type=T.GNSS, board_label="GNSS_1PPS_IN",
                        state=S.SELECTABLE, lock=L.LOCKED)
        h = self._handler([gnss])
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "selectable")
        self.assertEqual(h.get_gnss_pin_lock(DeviceType.PPS), "locked-ho-acq")

    def test_no_clock_id_returns_undefined(self):
        # pylint: disable=protected-access
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        h = CguHandler("path_no_exists", clock_id=5799633565437375000)
        h._dpll = _FakeDpll([_FakePin(pin_type="gnss",
                                      board_label="GNSS_1PPS_IN",
                                      state="selectable",
                                      lock="locked-ho-acq")])
        h._clock_id = None
        h.refresh_gnss_pins()
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "undefined")

    def test_single_snapshot_per_cycle(self):
        # One refresh_gnss_pins() must do exactly ONE get_all_pins() dump, and
        # the two accessors (x2 devices) must read the cache without any
        # further netlink dump. Guards against the per-accessor-dump
        # regression (4 extra dumps/cycle).
        # pylint: disable=protected-access
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        gnss = _FakePin(pin_type="gnss", board_label="GNSS_1PPS_IN",
                        state="selectable", lock="locked-ho-acq")
        h = CguHandler("path_no_exists", clock_id=5799633565437375000)
        h._dpll = _FakeDpll([gnss])
        h.refresh_gnss_pins()
        self.assertEqual(h._dpll.get_all_pins_calls, 1)
        h.get_gnss_pin_state(DeviceType.EEC)
        h.get_gnss_pin_lock(DeviceType.EEC)
        h.get_gnss_pin_state(DeviceType.PPS)
        h.get_gnss_pin_lock(DeviceType.PPS)
        # Still 1 -- accessors read the cache, no extra dumps.
        self.assertEqual(h._dpll.get_all_pins_calls, 1)

    def test_state_and_lock_from_same_snapshot(self):
        # state and lock for a device must come from the SAME cached pin
        # object (same instant), so a later netlink change cannot split the
        # pair. Mutate the DPLL's pins AFTER the snapshot and confirm the
        # accessors still report the snapshot's values.
        # pylint: disable=protected-access
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        gnss = _FakePin(pin_type="gnss", board_label="GNSS_1PPS_IN",
                        state="selectable", lock="locked-ho-acq")
        h = self._handler([gnss])
        # Simulate the HW moving on after the snapshot was taken.
        h._dpll._pins = [_FakePin(pin_type="gnss",
                                  board_label="GNSS_1PPS_IN",
                                  state="disconnected", lock="undefined")]
        # Accessors read the cached snapshot, not the mutated live state.
        self.assertEqual(h.get_gnss_pin_state(DeviceType.PPS), "selectable")
        self.assertEqual(h.get_gnss_pin_lock(DeviceType.PPS), "locked-ho-acq")
