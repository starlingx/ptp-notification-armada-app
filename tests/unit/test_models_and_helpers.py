"""
Unit tests for trackingfunctionsdk model DTOs
and helpers.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import json
import tempfile
import unittest
from unittest import mock



class TestPtpState(unittest.TestCase):
    """Tests for PtpState model."""

    def test_state_values(self):
        """Test PtpState enum values exist."""
        from trackingfunctionsdk.model.dto \
            .ptpstate import PtpState
        self.assertIsNotNone(PtpState.Locked)
        self.assertIsNotNone(PtpState.Freerun)
        self.assertIsNotNone(PtpState.Holdover)

    def test_enum_type(self):
        """Test EnumPtpState is defined."""
        from trackingfunctionsdk.model.dto \
            .ptpstate import EnumPtpState
        self.assertIsNotNone(EnumPtpState)


class TestGnssState(unittest.TestCase):
    """Tests for GnssState model."""

    def test_state_values(self):
        """Test GnssState enum values."""
        from trackingfunctionsdk.model.dto \
            .gnssstate import GnssState
        self.assertEqual(
            GnssState.Synchronized,
            "SYNCHRONIZED")
        self.assertEqual(
            GnssState.Failure_Nofix,
            "FAILURE-NOFIX")
        self.assertEqual(
            GnssState.Holdover, "HOLDOVER")
        self.assertEqual(
            GnssState.Acquiring_Sync,
            "ACQUIRING-SYNC")
        self.assertEqual(
            GnssState.Antenna_Disconnected,
            "ANTENNA-DISCONNECTED")
        self.assertEqual(
            GnssState.Booting, "BOOTING")
        self.assertEqual(
            GnssState.Antenna_Short_Circuit,
            "ANTENNA-SHORT-CIRCUIT")
        self.assertEqual(
            GnssState.Failure_Low_SNR,
            "FAILURE-LOW-SNR")
        self.assertEqual(
            GnssState.Failure_PLL,
            "FAILURE-PLL")


class TestOsClockState(unittest.TestCase):
    """Tests for OsClockState model."""

    def test_state_values(self):
        """Test OsClockState enum values."""
        from trackingfunctionsdk.model.dto \
            .osclockstate import OsClockState
        self.assertEqual(
            OsClockState.Locked, "Locked")
        self.assertEqual(
            OsClockState.Freerun, "Freerun")
        self.assertEqual(
            OsClockState.Holdover, "Holdover")


class TestOverallClockState(unittest.TestCase):
    """Tests for OverallClockState model."""

    def test_state_values(self):
        """Test OverallClockState enum values."""
        from trackingfunctionsdk.model.dto \
            .overallclockstate import (
                OverallClockState)
        self.assertEqual(
            OverallClockState.Locked, "Locked")
        self.assertEqual(
            OverallClockState.Freerun, "Freerun")
        self.assertEqual(
            OverallClockState.Holdover,
            "Holdover")


class TestResourceType(unittest.TestCase):
    """Tests for ResourceType model."""

    def test_type_values(self):
        """Test ResourceType values."""
        from trackingfunctionsdk.model.dto \
            .resourcetype import ResourceType
        self.assertEqual(
            ResourceType.TypePTP, "PTP")
        self.assertEqual(
            ResourceType.TypeFPGA, "FPGA")
        self.assertEqual(
            ResourceType.TypeGNSS, "GNSS")

    def test_enum_type(self):
        """Test EnumResourceType is defined."""
        from trackingfunctionsdk.model.dto \
            .resourcetype import (
                EnumResourceType)
        self.assertIsNotNone(EnumResourceType)


class TestRpcEndpointInfo(unittest.TestCase):
    """Tests for RpcEndpointInfo model."""

    def test_init(self):
        """Test RpcEndpointInfo initialization."""
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import RpcEndpointInfo
        broker_url = (
            'rabbit://admin:admin'
            '@127.0.0.1:5672/')
        endpoint = RpcEndpointInfo(broker_url)
        self.assertEqual(
            endpoint.TransportEndpoint,
            broker_url)
        self.assertEqual(
            endpoint.Version, '1.0')
        self.assertEqual(
            endpoint.Namespace, 'notification')
        self.assertEqual(
            endpoint.Exchange,
            'notification_exchange')

    def test_to_dict(self):
        """Test RpcEndpointInfo to_dict method."""
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import RpcEndpointInfo
        broker_url = (
            'rabbit://test:test@localhost:5672/')
        endpoint = RpcEndpointInfo(broker_url)
        result = endpoint.to_dict()
        self.assertIsInstance(result, dict)
        self.assertEqual(
            result['TransportEndpoint'],
            broker_url)
        self.assertEqual(
            result['Version'], '1.0')
        self.assertIn('Namespace', result)
        self.assertIn('Exchange', result)
        self.assertIn('Topic', result)
        self.assertIn('Server', result)

    def test_rpc_endpoint_base(self):
        """Test RPC_ENDPOINT_BASE defaults."""
        from trackingfunctionsdk.model.dto \
            .rpc_endpoint import (
                RPC_ENDPOINT_BASE)
        self.assertEqual(
            RPC_ENDPOINT_BASE['Version'], '1.0')
        self.assertEqual(
            RPC_ENDPOINT_BASE['Namespace'],
            'notification')


class TestPtpStatus(unittest.TestCase):
    """Tests for PtpStatus model."""

    def test_to_dict(self):
        """Test PtpStatus to_dict method."""
        from trackingfunctionsdk.model.dto \
            .ptpstatus import PtpStatus
        from trackingfunctionsdk.model.dto \
            .ptpstate import PtpState
        status = PtpStatus()
        status.EventTimestamp = 1234567890.0
        status.ResourceType = "PTP"
        status.EventData_State = PtpState()
        status.ResourceQualifier_NodeName = (
            "controller-0")
        self.assertIsNotNone(status)


class TestConstants(unittest.TestCase):
    """Tests for constants module."""

    def test_phc_states(self):
        """Test PHC state constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.FREERUN_PHC_STATE,
            "Freerun")
        self.assertEqual(
            constants.LOCKED_PHC_STATE,
            "Locked")
        self.assertEqual(
            constants.HOLDOVER_PHC_STATE,
            "Holdover")
        self.assertEqual(
            constants.UNKNOWN_PHC_STATE,
            "Unknown")

    def test_pmc_constants(self):
        """Test PMC command constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.PORT_STATE, "portState")
        self.assertEqual(
            constants.GM_PRESENT, "gmPresent")
        self.assertEqual(
            constants.MASTER_OFFSET,
            "master_offset")
        self.assertEqual(
            constants.GM_CLOCK_CLASS,
            "gm.ClockClass")
        self.assertEqual(
            constants.TIME_TRACEABLE,
            "timeTraceable")

    def test_clock_class_values(self):
        """Test clock class constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.CLOCK_CLASS_VALUE6, "6")
        self.assertEqual(
            constants.CLOCK_CLASS_VALUE7, "7")
        self.assertEqual(
            constants.CLOCK_CLASS_VALUE135,
            "135")
        self.assertIn(
            "6",
            constants.CLOCK_CLASS_LOCKED_LIST)
        self.assertIn(
            "7",
            constants.CLOCK_CLASS_LOCKED_LIST)

    def test_source_sync_constants(self):
        """Test source sync path constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.SOURCE_SYNC_ALL, '/sync')
        self.assertTrue(
            constants
            .SOURCE_SYNC_GNSS_SYNC_STATUS
            .startswith('/sync/'))
        self.assertTrue(
            constants
            .SOURCE_SYNC_PTP_CLOCK_CLASS
            .startswith('/sync/'))
        self.assertTrue(
            constants
            .SOURCE_SYNC_PTP_LOCK_STATE
            .startswith('/sync/'))
        self.assertTrue(
            constants.SOURCE_SYNC_OS_CLOCK
            .startswith('/sync/'))

    def test_tolerance_constants(self):
        """Test tolerance threshold constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertIsInstance(
            constants.PHC2SYS_TOLERANCE_LOW,
            int)
        self.assertIsInstance(
            constants.PHC2SYS_TOLERANCE_HIGH,
            int)
        self.assertIsInstance(
            constants.PHC2SYS_TOLERANCE_THRESHOLD,
            int)
        self.assertLess(
            constants.PHC2SYS_TOLERANCE_LOW,
            constants.PHC2SYS_TOLERANCE_HIGH)

    def test_notification_format_constants(self):
        """Test notification format constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertIsNotNone(
            constants.SPEC_VERSION)
        self.assertIsNotNone(
            constants.DATA_VERSION)
        self.assertEqual(
            constants.DATA_TYPE_NOTIFICATION,
            "notification")
        self.assertEqual(
            constants.DATA_TYPE_METRIC,
            "metric")

    def test_clock_source_type(self):
        """Test ClockSourceType class."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.ClockSourceType.TypePTP,
            "PTP")
        self.assertEqual(
            constants.ClockSourceType.TypeGNSS,
            "GNSS")
        self.assertEqual(
            constants.ClockSourceType.TypeNA,
            "NA")

    def test_default_holdover(self):
        """Test default holdover seconds."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.DEFAULT_HOLDOVER_SECONDS,
            30)

    def test_threshold_type_constants(self):
        """Test threshold type constants."""
        from trackingfunctionsdk.common.helpers \
            import constants
        self.assertEqual(
            constants.THRESHOLD_TYPE_MAJOR,
            "major")
        self.assertEqual(
            constants.THRESHOLD_TYPE_MINOR,
            "minor")


class TestLogHelper(unittest.TestCase):
    """Tests for log_helper module."""

    def test_get_logger(self):
        """Test get_logger returns a logger."""
        from trackingfunctionsdk.common.helpers \
            import log_helper
        logger = log_helper.get_logger(
            'test_module')
        self.assertIsNotNone(logger)
        self.assertEqual(
            logger.name, 'test_module')

    def test_config_logger(self):
        """Test config_logger configures logger."""
        import logging
        from trackingfunctionsdk.common.helpers \
            import log_helper
        logger = logging.getLogger('test_config')
        result = log_helper.config_logger(logger)
        self.assertIsNotNone(result)


class TestPtpsyncUtilities(unittest.TestCase):
    """Tests for ptpsync utility functions."""

    def test_parse_resource_address(self):
        """Test parse_resource_address."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        resource_path = (
            '/cluster1/node1'
            '/sync/ptp-status/lock-state')
        cluster, node, resource = (
            ptpsync.parse_resource_address(
                resource_path))
        self.assertEqual(cluster, 'cluster1')
        self.assertEqual(node, 'node1')
        self.assertEqual(
            resource,
            '/sync/ptp-status/lock-state')

    def test_format_resource_no_instance(self):
        """Test format_resource_address."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        result = ptpsync.format_resource_address(
            'controller-0',
            '/sync/ptp-status/lock-state')
        expected = (
            '/./' + 'controller-0'
            + '/sync/ptp-status/lock-state')
        self.assertEqual(result, expected)

    def test_format_resource_with_instance(self):
        """Test format with instance name."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        result = ptpsync.format_resource_address(
            'controller-0',
            '/sync/ptp-status/lock-state',
            'ptp4l-inst1')
        self.assertIn('controller-0', result)
        self.assertIn('ptp4l-inst1', result)

    def test_check_critical_missing(self):
        """Test check_critical_resources miss."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        pmc, ptp4l, phc2sys, ptp4lconf = (
            ptpsync.check_critical_resources(
                'nonexistent-service',
                'nonexistent-phc2sys'))
        self.assertFalse(ptp4l)
        self.assertFalse(phc2sys)
        self.assertFalse(ptp4lconf)

    def test_run_shell2(self):
        """Test run_shell2 function."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        out, err, errcode = (
            ptpsync.run_shell2(
                '.', None, 'echo hello'))
        self.assertEqual(errcode, 0)
        self.assertIn(b'hello', out)

    def test_run_shell2_failure(self):
        """Test run_shell2 with failing cmd."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        out, err, errcode = (
            ptpsync.run_shell2(
                '.', None, 'false'))
        self.assertNotEqual(errcode, 0)

    def test_check_results_locked(self):
        """Test check_results Locked state."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'gm-id-1',
            constants.CLOCK_IDENTITY:
                'clock-id-2',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'slave',
        }
        sync_state, sync_source = (
            ptpsync.check_results(
                result, 8, 1))
        self.assertEqual(
            sync_state,
            constants.LOCKED_PHC_STATE)

    def test_check_results_freerun_no_gm(self):
        """Test Freerun when GM not present."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'false',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'gm-id-1',
            constants.CLOCK_IDENTITY:
                'clock-id-2',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'slave',
        }
        sync_state, _ = (
            ptpsync.check_results(
                result, 8, 1))
        self.assertEqual(
            sync_state,
            constants.FREERUN_PHC_STATE)

    def test_check_results_incomplete(self):
        """Test RuntimeError on incomplete."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        with self.assertRaises(RuntimeError):
            ptpsync.check_results({}, 8, 1)

    def test_check_results_local_gm(self):
        """Test local GM gives GNSS source."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'same-id',
            constants.CLOCK_IDENTITY:
                'same-id',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'master',
        }
        sync_state, sync_source = (
            ptpsync.check_results(
                result, 8, 1))
        self.assertEqual(
            sync_source,
            constants.ClockSourceType.TypeGNSS)

    def test_check_results_offset_exceeded(self):
        """Test Freerun on offset exceeded."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '5000000',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'gm-id-1',
            constants.CLOCK_IDENTITY:
                'clock-id-2',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'slave',
        }
        sync_state, _ = (
            ptpsync.check_results(
                result, 8, 1,
                offset_threshold=1000))
        self.assertEqual(
            sync_state,
            constants.FREERUN_PHC_STATE)

    def test_check_results_bad_clock_class(self):
        """Test Freerun on bad clock class."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '248',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'gm-id-1',
            constants.CLOCK_IDENTITY:
                'clock-id-2',
            constants.CLOCK_CLASS: '248',
            constants.PORT.format(1): 'slave',
        }
        sync_state, _ = (
            ptpsync.check_results(
                result, 8, 1))
        self.assertEqual(
            sync_state,
            constants.FREERUN_PHC_STATE)

    def test_check_results_no_slave_port(self):
        """Test Freerun with no slave port."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        from trackingfunctionsdk.common.helpers \
            import constants
        result = {
            constants.GM_PRESENT: 'true',
            constants.MASTER_OFFSET: '50',
            constants.GM_CLOCK_CLASS: '6',
            constants.TIME_TRACEABLE: '1',
            constants.GRANDMASTER_IDENTITY:
                'gm-id-1',
            constants.CLOCK_IDENTITY:
                'clock-id-2',
            constants.CLOCK_CLASS: '6',
            constants.PORT.format(1): 'master',
        }
        sync_state, _ = (
            ptpsync.check_results(
                result, 8, 1))
        self.assertEqual(
            sync_state,
            constants.FREERUN_PHC_STATE)

    def test_get_phc_index_missing_file(self):
        """Test get_phc_index missing file."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        result = ptpsync.get_phc_index(
            'nonexistent-iface')
        self.assertEqual(result, '')

    def test_get_interface_phc_device_miss(self):
        """Test get_interface_phc_device miss."""
        from trackingfunctionsdk.common.helpers \
            import ptpsync
        result = ptpsync.get_interface_phc_device(
            'nonexistent-iface')
        self.assertIsNone(result)


class TestInstanceConfigParser(unittest.TestCase):
    """Tests for instance_config_parser."""

    def test_holdover_time_default(self):
        """Test holdover returns default."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_holdover_time(
                'nonexistent', 30))
        self.assertEqual(result, 30)

    @mock.patch.dict(
        os.environ,
        {'PTP_HOLDOVER_SECONDS': '120'})
    def test_holdover_time_env_override(self):
        """Test holdover from env variable."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_holdover_time(
                'test-instance', 30))
        self.assertEqual(result, 120)

    @mock.patch.dict(
        os.environ,
        {'PTP_HOLDOVER_SECONDS': 'invalid'})
    def test_holdover_time_invalid_env(self):
        """Test holdover with invalid env."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_holdover_time(
                'test-instance', 30))
        self.assertIsInstance(result, int)

    def test_holdover_time_from_config(self):
        """Test holdover from config file."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[test-instance]\n"
                "holdover_seconds 60\n")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_holdover_time(
                        'test-instance', 30))
                self.assertEqual(result, 60)
        finally:
            os.unlink(config_path)

    def test_gnss_holdover_default(self):
        """Test GNSS holdover returns default."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_gnss_holdover_time(
                'nonexistent', 30))
        self.assertEqual(result, 30)

    @mock.patch.dict(
        os.environ,
        {'GNSS_HOLDOVER_SECONDS': '90'})
    def test_gnss_holdover_env(self):
        """Test GNSS holdover from env."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_gnss_holdover_time(
                'test', 30))
        self.assertEqual(result, 90)

    def test_osclock_holdover_default(self):
        """Test OS clock holdover default."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_osclock_holdover_time(
                'nonexistent', 30))
        self.assertEqual(result, 30)

    @mock.patch.dict(
        os.environ,
        {'OS_CLOCK_HOLDOVER_SECONDS': '45'})
    def test_osclock_holdover_env(self):
        """Test OS clock holdover from env."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_osclock_holdover_time(
                'test', 30))
        self.assertEqual(result, 45)

    def test_overall_holdover_default(self):
        """Test overall holdover default."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_overall_holdover_time(30))
        self.assertEqual(result, 30)

    @mock.patch.dict(
        os.environ,
        {'OVERALL_HOLDOVER_SECONDS': '100'})
    def test_overall_holdover_env(self):
        """Test overall holdover from env."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_overall_holdover_time(30))
        self.assertEqual(result, 100)

    @mock.patch.dict(
        os.environ,
        {'OVERALL_HOLDOVER_SECONDS': 'bad'})
    def test_overall_holdover_invalid_env(self):
        """Test overall holdover invalid env."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_overall_holdover_time(30))
        self.assertEqual(result, 30)

    def test_offset_threshold_major(self):
        """Test offset threshold major type."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[test-instance]\n"
                "offset_threshold_major_nsec"
                " 500\n")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_offset_threshold(
                        'test-instance',
                        'major', 1000))
                self.assertEqual(result, 500)
        finally:
            os.unlink(config_path)

    def test_offset_threshold_minor(self):
        """Test offset threshold minor type."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[test-instance]\n"
                "offset_threshold_minor_nsec"
                " 200\n")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_offset_threshold(
                        'test-instance',
                        'minor', 1000))
                self.assertEqual(result, 200)
        finally:
            os.unlink(config_path)

    def test_offset_threshold_unknown(self):
        """Test offset threshold unknown type."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        result = (
            instance_config_parser
            .get_instance_offset_threshold(
                'test', 'unknown', 1000))
        self.assertEqual(result, 1000)

    def test_config_value_parse_error(self):
        """Test config with invalid value."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "[test-instance]\n"
                "holdover_seconds"
                " not_a_number\n")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_holdover_time(
                        'test-instance', 30))
                self.assertEqual(result, 30)
        finally:
            os.unlink(config_path)

    def test_config_value_empty_file(self):
        """Test config with empty file."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write("")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_holdover_time(
                        'test-instance', 30))
                self.assertEqual(result, 30)
        finally:
            os.unlink(config_path)

    def test_config_comments_and_blanks(self):
        """Test config skips comments/blanks."""
        from trackingfunctionsdk.common.helpers \
            import instance_config_parser
        from trackingfunctionsdk.common.helpers \
            import constants
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.conf',
                delete=False) as tmp_file:
            tmp_file.write(
                "# This is a comment\n"
                "\n"
                "[test-instance]\n"
                "# Another comment\n"
                "holdover_seconds 75\n")
            config_path = tmp_file.name
        try:
            with mock.patch.object(
                    constants,
                    'INSTANCE_CONFIG_PATH',
                    config_path):
                result = (
                    instance_config_parser
                    .get_instance_holdover_time(
                        'test-instance', 30))
                self.assertEqual(result, 75)
        finally:
            os.unlink(config_path)


if __name__ == '__main__':
    unittest.main()
