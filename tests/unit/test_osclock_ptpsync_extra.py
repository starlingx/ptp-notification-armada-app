"""
Additional coverage tests for os_clock_monitor and ptpsync utility functions.
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
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers.os_clock_monitor import OsClockMonitor


class TestOsClockMonitorInit:
    """Test OsClockMonitor initialization with init=False."""

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_init_basic(self):
        # set_phc2sys_instance splits by PHC2SYS_CONFIG_PATH + "phc2sys-"
        config_path = constants.PHC2SYS_CONFIG_PATH + 'phc2sys-test-inst.conf'
        mon = OsClockMonitor(config_path, init=False)
        assert mon.phc2sys_instance == 'test-inst'

    @mock.patch.dict(os.environ,
                     {'PHC2SYS_TOLERANCE_THRESHOLD': '500'}, clear=False)
    def test_init_with_tolerance_env(self):
        config_path = constants.PHC2SYS_CONFIG_PATH + 'phc2sys-inst2.conf'
        mon = OsClockMonitor(config_path, init=False)
        assert mon.phc2sys_tolerance_threshold == 500


class TestPtpsyncGetPhcIndex:
    """Test get_phc_index function."""

    def test_get_phc_index_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'ptp-interfaces.conf')
            with open(config_path, 'w') as f:
                f.write("[ens1f0]\n")
                f.write("phc_index 3\n")
            with mock.patch.object(constants, 'PTP_CONFIG_PATH',
                                   tmpdir + '/'):
                result = utils.get_phc_index('ens1f0')
                assert result == '3'

    def test_get_phc_index_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, 'ptp-interfaces.conf')
            with open(config_path, 'w') as f:
                f.write("[other_interface]\n")
                f.write("phc_index 5\n")
            with mock.patch.object(constants, 'PTP_CONFIG_PATH',
                                   tmpdir + '/'):
                result = utils.get_phc_index('ens1f0')
                assert result == ''

    def test_get_phc_index_file_missing(self):
        with mock.patch.object(constants, 'PTP_CONFIG_PATH',
                               '/nonexistent/'):
            result = utils.get_phc_index('ens1f0')
            assert result == ''


class TestPtpsyncGetTs2phcLeapfile:
    """Test leapfile path is read from constants."""

    def test_get_leapfile_path_from_constants(self):
        # Verify the LEAP_FILE_PATH constant is used by
        # get_latest_offset_from_leapfile (no separate lookup function)
        assert constants.LEAP_FILE_PATH == \
            '/ptp/linuxptp/ptpinstance/leap-seconds.list'


class TestPtpsyncGetLatestOffsetFromLeapfile:
    """Test get_latest_offset_from_leapfile."""

    def test_valid_leapfile(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.list',
                                         delete=False) as f:
            f.write("# comment line\n")
            f.write("#$\t 37\n")
            f.write("2272060800\t10\t# 1 Jan 1972\n")
            f.write("3439756800\t37\t# 1 Jan 2017\n")
            fname = f.name
        try:
            with mock.patch.object(constants, 'LEAP_FILE_PATH', fname):
                result = utils.get_latest_offset_from_leapfile()
                assert result == 37
        finally:
            os.unlink(fname)

    def test_leapfile_missing(self):
        with mock.patch.object(constants, 'LEAP_FILE_PATH',
                               '/nonexistent/file'):
            result = utils.get_latest_offset_from_leapfile()
            assert result is None


class TestPtpsyncFormatResourceAddress:
    """Test format_resource_address function."""

    def test_format_with_instance(self):
        result = utils.format_resource_address(
            'host1', '/.sync/sync-status/sync-state', 'ptp4l-inst1')
        assert 'host1' in result
        assert 'ptp4l-inst1' in result
        assert result == '/./' + 'host1' + '/' + 'ptp4l-inst1' + \
            '/.sync/sync-status/sync-state'

    def test_format_without_instance(self):
        result = utils.format_resource_address(
            'host1', '/.sync/sync-status/sync-state')
        assert 'host1' in result
        assert result == '/./' + 'host1' + '/.sync/sync-status/sync-state'
