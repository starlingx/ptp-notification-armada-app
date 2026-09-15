#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import enum
import os
import unittest

import mock

from trackingfunctionsdk.common.helpers.gnss_monitor import GnssMonitor

testpath = os.environ.get("TESTPATH", "")


class GnssMonitorTests(unittest.TestCase):

    def test_check_config_file_interfaces(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        self.gnssmon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        self.assertEqual(
            self.gnssmon._check_config_file_interfaces(), [
                'ens1f0', 'ens2f0'])

    def test_set_ptp_devices(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        return_value=[]):
            self.gnssmon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        self.assertEqual(self.gnssmon.get_ptp_devices(), [])

        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        side_effect=[['/hostsys/class/net/ens1f0/device/ptp/ptp0'],
                                     ['/hostsys/class/net/ens2f0/device/ptp/ptp1']
                                     ]):
            self.gnssmon.set_ptp_devices()

        self.assertEqual(set(self.gnssmon.get_ptp_devices()),
                         set(['ptp0', 'ptp1']))

        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        side_effect=[['/hostsys/class/net/ens1f0/device/ptp/ptp0'],
                                     ['/hostsys/class/net/ens2f0/device/ptp/ptp0']
                                     ]):
            self.gnssmon.set_ptp_devices()

        self.assertEqual(self.gnssmon.get_ptp_devices(), ['ptp0'])


class SetGnssStatusPinAwareTests(unittest.TestCase):
    """set_gnss_status() must only report Synchronized when the DPLL is locked
    to a GNSS pin, not to a SyncE (frequency-only) recovered-clock pin."""

    def _make_monitor(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        return_value=[]):
            mon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        mon.ts2phc_service_name = 'ts1'
        mon.gnss_cgu_handler = mock.MagicMock()
        from trackingfunctionsdk.common.helpers import constants
        mon.gnss_cgu_handler.get_eec_status.return_value = \
            constants.GNSS_LOCKED_HO_ACQ
        mon.gnss_cgu_handler.get_pps_status.return_value = \
            constants.GNSS_LOCKED_HO_ACQ
        return mon

    def _set_pins(self, mon, eec_type, pps_type):
        h = mon.gnss_cgu_handler
        h.get_eec_pin_type.return_value = eec_type
        h.get_pps_pin_type.return_value = pps_type
        # current_ref values that are not the GNSS pin, so pin_type drives it
        h.get_eec_current_ref.return_value = 'other'
        h.get_pps_current_ref.return_value = 'other'

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_pins_report_synchronized(self, _isfile):
        mon = self._make_monitor()
        self._set_pins(mon, eec_type='gnss', pps_type='gnss')
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)

    @mock.patch('os.path.isfile', return_value=True)
    def test_synce_failover_reports_failure(self, _isfile):
        # DPLL locked-ho-acq but the active pins are SyncE (frequency only):
        # GNSS is gone, so this must NOT be reported as synchronized.
        mon = self._make_monitor()
        self._set_pins(mon, eec_type='synce-eth-port',
                       pps_type='synce-eth-port')
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_mixed_pps_synce_reports_failure(self, _isfile):
        # EEC on GNSS but PPS failed over to SyncE -> not fully GNSS locked.
        mon = self._make_monitor()
        self._set_pins(mon, eec_type='gnss', pps_type='synce-eth-port')
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_by_current_ref_reports_synchronized(self, _isfile):
        # Pin type undefined but current_ref is the GNSS pin -> synchronized.
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        h = mon.gnss_cgu_handler
        h.get_eec_pin_type.return_value = 'undefined'
        h.get_pps_pin_type.return_value = 'undefined'
        h.get_eec_current_ref.return_value = constants.GNSS_PIN
        h.get_pps_current_ref.return_value = constants.GNSS_PIN
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)


class _FakePinType(enum.Enum):
    """Mimic the pynetlink PinType enum returned by CguHandler on real HW.

    The runtime getters are annotated ``-> str`` but actually return a
    pynetlink enum whose ``.value`` is the string (e.g. 'gnss'). Comparing
    the enum object directly to the string 'gnss' is always False, which is
    the exact condition that regressed GNSS detection on hardware while the
    string-based unit tests kept passing.
    """
    GNSS = 'gnss'
    SYNCE_ETH_PORT = 'synce-eth-port'


class SetGnssStatusEnumPinTypeTests(unittest.TestCase):
    """Regression: pin_type is a PinType enum on real hardware, not a str.

    These tests feed the enum (and GNR-D board-label variant) so the
    enum-vs-string comparison bug cannot silently return.
    """

    def _make_monitor(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        return_value=[]):
            mon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        mon.ts2phc_service_name = 'ts1'
        mon.gnss_cgu_handler = mock.MagicMock()
        from trackingfunctionsdk.common.helpers import constants
        mon.gnss_cgu_handler.get_eec_status.return_value = \
            constants.GNSS_LOCKED_HO_ACQ
        mon.gnss_cgu_handler.get_pps_status.return_value = \
            constants.GNSS_LOCKED_HO_ACQ
        return mon

    @mock.patch('os.path.isfile', return_value=True)
    def test_enum_pin_type_gnss_reports_synchronized(self, _isfile):
        # Sanity guard: enum PinType.GNSS != 'gnss' by identity comparison.
        self.assertNotEqual(_FakePinType.GNSS, 'gnss')
        mon = self._make_monitor()
        h = mon.gnss_cgu_handler
        h.get_eec_pin_type.return_value = _FakePinType.GNSS
        h.get_pps_pin_type.return_value = _FakePinType.GNSS
        # current_ref is not a GNSS label, so pin_type must drive the result
        h.get_eec_current_ref.return_value = 'other'
        h.get_pps_current_ref.return_value = 'other'
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)

    @mock.patch('os.path.isfile', return_value=True)
    def test_enum_synce_pin_type_reports_failure(self, _isfile):
        mon = self._make_monitor()
        h = mon.gnss_cgu_handler
        h.get_eec_pin_type.return_value = _FakePinType.SYNCE_ETH_PORT
        h.get_pps_pin_type.return_value = _FakePinType.SYNCE_ETH_PORT
        h.get_eec_current_ref.return_value = 'other'
        h.get_pps_current_ref.return_value = 'other'
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnrd_board_label_reports_synchronized(self, _isfile):
        # GNR-D/E825 reports board label 'GNSS_1PPS_IN' and pin_type undefined;
        # label fallback must still recognize it as GNSS.
        mon = self._make_monitor()
        h = mon.gnss_cgu_handler
        h.get_eec_pin_type.return_value = 'undefined'
        h.get_pps_pin_type.return_value = 'undefined'
        h.get_eec_current_ref.return_value = 'GNSS_1PPS_IN'
        h.get_pps_current_ref.return_value = 'GNSS_1PPS_IN'
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)
