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
from pynetlink import DpllPins, LockStatus, NetlinkDPLL
testpath = os.environ.get("TESTPATH", "")

class CguHandlerTests(unittest.TestCase):
    """Tests for `CguHandler` class, including Netlink communication."""

    reference_pins = None
    reference_pins_selectable = None

    @classmethod
    def setUpClass(cls):
        reference_pin = [ {
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
        } ]
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
        test_cgu_handler._pins = None # pylint: disable=W0212

        # Call read_cgu considering that the object has no pins
        test_cgu_handler.read_cgu()

        self.assertEqual(test_cgu_handler._pins, # pylint: disable=W0212
                         self.reference_pins)

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

        # Read reference pins
        test_cgu_handler._pins = self.reference_pins # pylint: disable=W0212
        # Call read function. The individual reading will load one pin in
        # selectable status, forcing a full reading.
        test_cgu_handler.read_cgu()

        self.assertEqual(test_cgu_handler._pins, # pylint: disable=W0212
                         self.reference_pins)

        mock_get_pins_by_id.assert_called_once_with(30)
        mock_get_all_pins.assert_called_once()

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
