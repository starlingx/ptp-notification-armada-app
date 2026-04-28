"""
Unit tests for synce_monitor module.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import tempfile
from unittest import mock

import pytest

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers.synce_monitor import (
    SynceMonitor,
    SynceState,
)
from pynetlink import DeviceType, LockStatus


class TestSynceState:
    """Test SynceState constants."""

    def test_state_values(self):
        assert SynceState.Locked == "Locked"
        assert SynceState.Holdover == "Holdover"
        assert SynceState.Freerun == "Freerun"
        assert SynceState.Unknown == "Unknown"


class TestSynceMonitorInit:
    """Test SynceMonitor initialization."""

    @mock.patch.object(SynceMonitor, '_parse_monitoring_config',
                       return_value={})
    @mock.patch.object(SynceMonitor, '_parse_clock_id', return_value=42)
    def test_init_defaults(self, mock_clock, mock_monitoring):
        mon = SynceMonitor('test-instance')
        assert mon.synce4l_service_name == 'test-instance'
        assert mon.holdover_time == 30
        assert mon._dpll is None
        assert mon._clock_id == 42
        assert mon._locked_ql == 0x02
        assert mon._holdover_ql == 0x04
        assert mon._freerun_ql == 0x0f
        assert mon._sync_state == SynceState.Unknown
        assert mon._holdover_start is None
        assert mon._last_ql is None

    @mock.patch.object(SynceMonitor, '_parse_monitoring_config',
                       return_value={'static_ql': 0x01,
                                     'holdover_ql': 0x03,
                                     'freerun_ql': 0x0e})
    @mock.patch.object(SynceMonitor, '_parse_clock_id', return_value=10)
    def test_init_with_monitoring_config(self, mock_clock, mock_monitoring):
        mon = SynceMonitor('inst1', holdover_time=60)
        assert mon.holdover_time == 60
        assert mon._locked_ql == 0x01
        assert mon._holdover_ql == 0x03
        assert mon._freerun_ql == 0x0e

    @mock.patch.object(SynceMonitor, '_parse_monitoring_config',
                       return_value={})
    @mock.patch.object(SynceMonitor, '_parse_clock_id', return_value=5)
    def test_init_with_explicit_ql(self, mock_clock, mock_monitoring):
        mon = SynceMonitor('inst1', locked_ql=0x10,
                           holdover_ql=0x20, freerun_ql=0x30)
        assert mon._locked_ql == 0x10
        assert mon._holdover_ql == 0x20
        assert mon._freerun_ql == 0x30


class TestSynceMonitorParseClockId:
    """Test _parse_clock_id method."""

    def test_parse_clock_id_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'synce4l-myinst.conf')
            with open(config_path, 'w') as f:
                f.write("[<myinst>]\n")
                f.write("clock_id 123\n")
            with mock.patch.object(constants, 'PTP_CONFIG_PATH', tmpdir + '/'):
                mon = SynceMonitor.__new__(SynceMonitor)
                result = mon._parse_clock_id('myinst')
                assert result == 123

    def test_parse_clock_id_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'synce4l-myinst.conf')
            with open(config_path, 'w') as f:
                f.write("[global]\n")
                f.write("some_key value\n")
            with mock.patch.object(constants, 'PTP_CONFIG_PATH', tmpdir + '/'):
                mon = SynceMonitor.__new__(SynceMonitor)
                result = mon._parse_clock_id('myinst')
                assert result is None

    def test_parse_clock_id_file_missing(self):
        with mock.patch.object(constants, 'PTP_CONFIG_PATH',
                               '/nonexistent/path/'):
            mon = SynceMonitor.__new__(SynceMonitor)
            result = mon._parse_clock_id('missing')
            assert result is None


class TestSynceMonitorParseMonitoringConfig:
    """Test _parse_monitoring_config method."""

    def test_parse_monitoring_config_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'instance-monitoring.conf')
            with open(config_path, 'w') as f:
                f.write("[myinst]\n")
                f.write("static_ql 0x01\n")
                f.write("holdover_ql 0x03\n")
                f.write("freerun_ql 0x0e\n")
            with mock.patch.object(constants, 'INSTANCE_CONFIG_PATH',
                                   config_path):
                mon = SynceMonitor.__new__(SynceMonitor)
                result = mon._parse_monitoring_config('myinst')
                assert result == {'static_ql': 1,
                                  'holdover_ql': 3,
                                  'freerun_ql': 14}

    def test_parse_monitoring_config_section_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'instance-monitoring.conf')
            with open(config_path, 'w') as f:
                f.write("[other-inst]\n")
                f.write("static_ql 0x01\n")
            with mock.patch.object(constants, 'INSTANCE_CONFIG_PATH',
                                   config_path):
                mon = SynceMonitor.__new__(SynceMonitor)
                result = mon._parse_monitoring_config('myinst')
                assert result == {}

    def test_parse_monitoring_config_file_missing(self):
        with mock.patch.object(constants, 'INSTANCE_CONFIG_PATH',
                               '/nonexistent/file.conf'):
            mon = SynceMonitor.__new__(SynceMonitor)
            result = mon._parse_monitoring_config('myinst')
            assert result == {}


class TestSynceMonitorGetDpll:
    """Test _get_dpll method."""

    @mock.patch('trackingfunctionsdk.common.helpers.synce_monitor.NetlinkDPLL')
    def test_get_dpll_creates_instance(self, mock_dpll_cls):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._dpll = None
        mock_dpll_cls.return_value = mock.Mock()
        result = mon._get_dpll()
        mock_dpll_cls.assert_called_once_with(True)
        assert result is not None

    @mock.patch('trackingfunctionsdk.common.helpers.synce_monitor.NetlinkDPLL')
    def test_get_dpll_reuses_existing(self, mock_dpll_cls):
        mon = SynceMonitor.__new__(SynceMonitor)
        existing = mock.Mock()
        mon._dpll = existing
        result = mon._get_dpll()
        mock_dpll_cls.assert_not_called()
        assert result is existing

    @mock.patch('trackingfunctionsdk.common.helpers.synce_monitor.NetlinkDPLL')
    def test_get_dpll_handles_exception(self, mock_dpll_cls):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._dpll = None
        mock_dpll_cls.side_effect = Exception("socket error")
        result = mon._get_dpll()
        assert result is None


class TestSynceMonitorReadEecStatus:
    """Test _read_eec_status method."""

    def test_read_eec_no_dpll(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._dpll = None
        mon._clock_id = 42
        mon.synce4l_service_name = 'test'
        with mock.patch.object(mon, '_get_dpll', return_value=None):
            result = mon._read_eec_status()
            assert result is None

    def test_read_eec_no_clock_id(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._dpll = mock.Mock()
        mon._clock_id = None
        mon.synce4l_service_name = 'test'
        with mock.patch.object(mon, '_get_dpll', return_value=mon._dpll):
            result = mon._read_eec_status()
            assert result is None

    def test_read_eec_device_found(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._clock_id = 42
        mon.synce4l_service_name = 'test'
        mock_device = mock.Mock()
        mock_device.dev_type = DeviceType.EEC
        mock_device.dev_clock_id = 42
        mock_device.lock_status = LockStatus.LOCKED
        mock_dpll = mock.Mock()
        mock_dpll.get_all_devices.return_value = [mock_device]
        mon._dpll = mock_dpll
        with mock.patch.object(mon, '_get_dpll', return_value=mock_dpll):
            result = mon._read_eec_status()
            assert result == LockStatus.LOCKED

    def test_read_eec_device_not_found(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._clock_id = 42
        mon.synce4l_service_name = 'test'
        mock_device = mock.Mock()
        mock_device.dev_type = DeviceType.EEC
        mock_device.dev_clock_id = 99  # different clock_id
        mock_dpll = mock.Mock()
        mock_dpll.get_all_devices.return_value = [mock_device]
        mon._dpll = mock_dpll
        with mock.patch.object(mon, '_get_dpll', return_value=mock_dpll):
            result = mon._read_eec_status()
            assert result is None

    def test_read_eec_exception(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._clock_id = 42
        mon.synce4l_service_name = 'test'
        mock_dpll = mock.Mock()
        mock_dpll.get_all_devices.side_effect = Exception("netlink err")
        mon._dpll = mock_dpll
        with mock.patch.object(mon, '_get_dpll', return_value=mock_dpll):
            result = mon._read_eec_status()
            assert result is None
            assert mon._dpll is None


class TestSynceMonitorGetSynceStatus:
    """Test get_synce_status method."""

    def _make_monitor(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon.synce4l_service_name = 'test'
        mon._clock_id = 42
        mon._dpll = None
        mon.holdover_time = 30
        mon._sync_state = SynceState.Unknown
        mon._event_time = 1000.0
        mon._holdover_start = None
        return mon

    def test_locked_status(self):
        mon = self._make_monitor()
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.LOCKED):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Locked
            assert new_event is True
            assert mon._holdover_start is None

    def test_locked_and_holdover_status(self):
        mon = self._make_monitor()
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.LOCKED_AND_HOLDOVER):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Locked

    def test_holdover_from_locked(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.HOLDOVER):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Holdover
            assert new_event is True
            assert mon._holdover_start is not None

    def test_holdover_within_time(self):
        import time
        mon = self._make_monitor()
        mon._sync_state = SynceState.Holdover
        mon._holdover_start = time.time() - 5  # 5 seconds ago
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.HOLDOVER):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Holdover
            assert new_event is False

    def test_holdover_expired(self):
        import time
        mon = self._make_monitor()
        mon._sync_state = SynceState.Holdover
        mon._holdover_start = time.time() - 60  # 60 seconds ago
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.HOLDOVER):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Freerun
            assert new_event is True

    def test_holdover_from_freerun(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Freerun
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.HOLDOVER):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Freerun
            assert new_event is False

    def test_unlocked_status(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.UNLOCKED):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Freerun
            assert new_event is True

    def test_read_failure_no_change(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        with mock.patch.object(mon, '_read_eec_status', return_value=None):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Locked
            assert new_event is False

    def test_no_state_change(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        with mock.patch.object(mon, '_read_eec_status',
                               return_value=LockStatus.LOCKED):
            new_event, state, _ = mon.get_synce_status()
            assert state == SynceState.Locked
            assert new_event is False


class TestSynceMonitorGetClockQuality:
    """Test get_clock_quality method."""

    def _make_monitor(self):
        mon = SynceMonitor.__new__(SynceMonitor)
        mon._locked_ql = 0x02
        mon._holdover_ql = 0x04
        mon._freerun_ql = 0x0f
        mon._last_ql = None
        mon._ql_event_time = 1000.0
        return mon

    def test_locked_ql(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        new_event, ql, _ = mon.get_clock_quality()
        assert new_event is True
        assert ql == 0x02

    def test_holdover_ql(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Holdover
        new_event, ql, _ = mon.get_clock_quality()
        assert new_event is True
        assert ql == 0x04

    def test_freerun_ql(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Freerun
        new_event, ql, _ = mon.get_clock_quality()
        assert new_event is True
        assert ql == 0x0f

    def test_unknown_ql(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Unknown
        new_event, ql, _ = mon.get_clock_quality()
        assert new_event is True
        assert ql == 0xff

    def test_no_change(self):
        mon = self._make_monitor()
        mon._sync_state = SynceState.Locked
        mon._last_ql = 0x02  # already set
        new_event, ql, _ = mon.get_clock_quality()
        assert new_event is False
        assert ql == 0x02
