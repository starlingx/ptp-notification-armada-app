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
    """set_gnss_status() must report Synchronized based on the GNSS reference
    pin's own health (present+locked), including when GNSS is a healthy
    standby (SELECTABLE) rather than the actively-selected master -- and must
    NOT report Synchronized when GNSS is lost and the DPLL has locked to a
    SyncE/backhaul pin instead."""

    def _make_monitor(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        return_value=[]):
            mon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        mon.ts2phc_service_name = 'ts1'
        mon.gnss_cgu_handler = mock.MagicMock()
        return mon

    def _set_gnss_pin(self, mon, eec_state, eec_lock, pps_state, pps_lock):
        """Program the GNSS reference pin's own state+lock per DPLL device."""
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        h = mon.gnss_cgu_handler

        def state(device_type):
            return eec_state if device_type == DeviceType.EEC else pps_state

        def lock(device_type):
            return eec_lock if device_type == DeviceType.EEC else pps_lock
        h.get_gnss_pin_state.side_effect = state
        h.get_gnss_pin_lock.side_effect = lock

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_primary_connected_reports_synchronized(self, _isfile):
        # Scenario 2 (GNSS primary): GNSS pin connected+locked on both
        # devices -> SYNCHRONIZED (unchanged behaviour).
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state=constants.GNSS_PIN_STATE_CONNECTED,
            eec_lock=constants.GNSS_LOCKED_HO_ACQ,
            pps_state=constants.GNSS_PIN_STATE_CONNECTED,
            pps_lock=constants.GNSS_LOCKED_HO_ACQ)
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_standby_selectable_reports_synchronized(self, _isfile):
        # THE FIX (PTP backhaul primary, GNSS secondary): EEC GNSS pin
        # connected+locked, PPS GNSS pin a healthy standby (SELECTABLE)+locked
        # while the active PPS master is the backhaul -> SYNCHRONIZED
        # (previously FAILURE-NOFIX).
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state=constants.GNSS_PIN_STATE_CONNECTED,
            eec_lock=constants.GNSS_LOCKED_HO_ACQ,
            pps_state=constants.GNSS_PIN_STATE_SELECTABLE,
            pps_lock=constants.GNSS_LOCKED_HO_ACQ)
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)

    @mock.patch('os.path.isfile', return_value=True)
    def test_synce_failover_reports_failure(self, _isfile):
        # GNSS lost -> no GNSS pin present (DPLL rode a SyncE/backhaul pin):
        # the GNSS accessors report the GNSS pin as undefined/disconnected, so
        # this must stay FAILURE-NOFIX (SyncE guard preserved).
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state='undefined', eec_lock='undefined',
            pps_state='undefined', pps_lock='undefined')
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_disconnected_reports_failure(self, _isfile):
        # Genuine GNSS loss: GNSS pin DISCONNECTED on both devices.
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state='disconnected', eec_lock=constants.GNSS_LOCKED_HO_ACQ,
            pps_state='disconnected', pps_lock=constants.GNSS_LOCKED_HO_ACQ)
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_gnss_selectable_but_unlocked_reports_failure(self, _isfile):
        # No false-healthy: a GNSS pin that is SELECTABLE but NOT locked
        # (acquiring / no fix) must NOT be reported synchronized.
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state=constants.GNSS_PIN_STATE_CONNECTED,
            eec_lock=constants.GNSS_LOCKED_HO_ACQ,
            pps_state=constants.GNSS_PIN_STATE_SELECTABLE,
            pps_lock='holdover')
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_eec_not_gnss_reports_failure(self, _isfile):
        # EEC GNSS pin not present (GNSS not disciplining frequency) while PPS
        # GNSS pin selectable+locked -> not fully GNSS healthy -> FAILURE.
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        self._set_gnss_pin(
            mon,
            eec_state='disconnected', eec_lock='undefined',
            pps_state=constants.GNSS_PIN_STATE_SELECTABLE,
            pps_lock=constants.GNSS_LOCKED_HO_ACQ)
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)

    @mock.patch('os.path.isfile', return_value=True)
    def test_ts2phc_not_running_reports_failure(self, _isfile_true):
        # ts2phc precheck unchanged: pid file absent -> FAILURE-NOFIX before
        # any pin inspection.
        from trackingfunctionsdk.common.helpers import constants
        mon = self._make_monitor()
        # Even with a perfectly healthy GNSS pin, the missing pid file wins.
        self._set_gnss_pin(
            mon,
            eec_state=constants.GNSS_PIN_STATE_CONNECTED,
            eec_lock=constants.GNSS_LOCKED_HO_ACQ,
            pps_state=constants.GNSS_PIN_STATE_CONNECTED,
            pps_lock=constants.GNSS_LOCKED_HO_ACQ)
        with mock.patch('os.path.isfile', return_value=False):
            mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Failure_Nofix)


class SetGnssStatusEnumStateTests(unittest.TestCase):
    """Regression: the GNSS pin state/lock are pynetlink enums on real
    hardware (whose ``.value`` is the string), not plain strings. The
    health check must compare by ``.value``."""

    def _make_monitor(self):
        cgu_path = testpath + "test_input_files/mock_cgu_output_logan_beach"
        gnss_config = testpath + "test_input_files/ts2phc_valid.conf"
        with mock.patch('trackingfunctionsdk.common.helpers.ptpsync.glob',
                        return_value=[]):
            mon = GnssMonitor(gnss_config, cgu_path=cgu_path)
        mon.ts2phc_service_name = 'ts1'
        mon.gnss_cgu_handler = mock.MagicMock()
        return mon

    @mock.patch('os.path.isfile', return_value=True)
    def test_enum_state_selectable_reports_synchronized(self, _isfile):
        # The CguHandler GNSS accessors already unwrap .value, but guard the
        # monitor against an enum leaking through: feed enum-like objects and
        # confirm a selectable+locked GNSS standby is Synchronized.
        from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
        from trackingfunctionsdk.common.helpers import constants

        class _Lock:
            value = constants.GNSS_LOCKED_HO_ACQ
        mon = self._make_monitor()
        h = mon.gnss_cgu_handler

        def state(device_type):
            return (_FakePinState.CONNECTED if device_type == DeviceType.EEC
                    else _FakePinState.SELECTABLE)

        def lock(_device_type):
            return _Lock()
        h.get_gnss_pin_state.side_effect = state
        h.get_gnss_pin_lock.side_effect = lock
        mon.set_gnss_status()
        from trackingfunctionsdk.model.dto.gnssstate import GnssState
        self.assertEqual(mon._state, GnssState.Synchronized)


class _FakePinType(enum.Enum):
    """Mimic the pynetlink PinType enum returned by CguHandler on real HW."""
    GNSS = 'gnss'
    SYNCE_ETH_PORT = 'synce-eth-port'


class _FakePinState(enum.Enum):
    """Mimic the pynetlink PinState enum (its ``.value`` is the string)."""
    CONNECTED = 'connected'
    SELECTABLE = 'selectable'
    DISCONNECTED = 'disconnected'


class IsTimeSourceLockedTests(unittest.TestCase):
    """is_time_source_locked() reports whether the DPLL is locked to ANY
    valid phase/time source (GNSS or an external/SDP 1PPS backhaul pin),
    used by the overall sync-state aggregation. SyncE (frequency-only),
    MUX and the internal oscillator must NOT count."""

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

    def test_gnss_pin_is_time_source_locked(self):
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = 'gnss'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'gnss'
        self.assertTrue(mon.is_time_source_locked())

    def test_gnss_pin_requires_eec_locked(self):
        # On a GNSS pin both EEC and PPS must be locked. If the EEC is not
        # locked-ho-acq, GNSS is not genuinely healthy -> not locked.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_status.return_value = 'holdover'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'gnss'
        self.assertFalse(mon.is_time_source_locked())

    def test_ext_backhaul_pin_is_time_source_locked(self):
        # After GNSS->SDP0 failover the DPLL phase/time (PPS) locks to the
        # backhaul pin (pin_type=ext) while the EEC is expected to remain in
        # holdover. PPS lock to the backhaul 1PPS is sufficient -- still a
        # valid phase/time source, so overall timing is healthy.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_status.return_value = 'holdover'
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = 'gnss'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'ext'
        self.assertTrue(mon.is_time_source_locked())

    def test_ext_backhaul_pin_requires_pps_locked(self):
        # On the backhaul (ext) pin the PPS must be locked; if it is not,
        # there is no valid phase/time lock -> not locked.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_pps_status.return_value = 'holdover'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'ext'
        self.assertFalse(mon.is_time_source_locked())

    def test_synce_pin_is_not_time_source_locked(self):
        # SyncE is frequency-only -- must NOT keep overall Locked.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = 'synce-eth-port'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'synce-eth-port'
        self.assertFalse(mon.is_time_source_locked())

    def test_not_device_locked_is_not_time_source_locked(self):
        # DPLL not locked-ho-acq -> False regardless of pin type.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_status.return_value = 'holdover'
        mon.gnss_cgu_handler.get_pps_status.return_value = 'holdover'
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = 'gnss'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'gnss'
        self.assertFalse(mon.is_time_source_locked())

    def test_pps_pin_type_drives_decision(self):
        # The active phase/time (PPS) pin type drives the decision. A PPS lock
        # to the backhaul (ext) counts even if the EEC pin reports a different
        # (frequency-only) source.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = 'synce-eth-port'
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'ext'
        self.assertTrue(mon.is_time_source_locked())

    def test_undefined_pin_type_is_not_time_source_locked(self):
        # Unknown/undefined PPS pin type (e.g. pynetlink-missing mock path)
        # contributes nothing -> False.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = 'undefined'
        self.assertFalse(mon.is_time_source_locked())

    def test_enum_pin_type_is_tolerated(self):
        # get_*_pin_type() returns a PinType enum on real hardware; the
        # method must compare by .value.
        mon = self._make_monitor()
        mon.gnss_cgu_handler.get_eec_pin_type.return_value = _FakePinType.GNSS
        mon.gnss_cgu_handler.get_pps_pin_type.return_value = _FakePinType.GNSS
        self.assertTrue(mon.is_time_source_locked())
