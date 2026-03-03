#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock
from unittest.mock import mock_open
from unittest.mock import patch

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers.instance_config_parser import (
    _get_instance_config_value
)
from trackingfunctionsdk.common.helpers.instance_config_parser import (
    get_instance_holdover_time
)
from trackingfunctionsdk.common.helpers.instance_config_parser import (
    get_instance_offset_threshold
)
from trackingfunctionsdk.common.helpers.instance_config_parser import (
    get_instance_osclock_holdover_time
)
from trackingfunctionsdk.common.helpers.instance_config_parser import (
    get_overall_holdover_time
)

# Mock pynetlink before importing constants
sys.modules['pynetlink'] = MagicMock()


class TestInstanceConfigParser(unittest.TestCase):

    def setUp(self):
        self.test_config_content = (
            "# Test config file\n"
            "[ptp4l-0]\n"
            "holdover_seconds 45\n"
            "offset_threshold_major_nsec 2000000\n"
            "offset_threshold_minor_nsec 1500\n\n"
            "[ts2phc-GNSS-1588]\n"
            "holdover_seconds 60\n"
            "offset_threshold_major_nsec 3000000\n\n"
            "[phc2sys-legacy]\n"
            "holdover_seconds 25\n"
            "offset_threshold_minor_nsec 800\n"
        )

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    def test_get_instance_holdover_time_file_not_found(self, mock_exists):
        """Test fallback to default when config file doesn't exist and no env var"""
        mock_exists.return_value = False
        with patch.dict(os.environ, {}, clear=True):
            result = get_instance_holdover_time('ptp4l-0', 30)
        self.assertEqual(result, 30)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_instance_holdover_time_success(self, mock_file, mock_exists):
        """Test successful reading of holdover time from config when no env var set"""
        mock_exists.return_value = True
        mock_file.return_value.read_data = self.test_config_content
        mock_file.return_value.__iter__ = lambda self: iter(
            self.read_data.splitlines())
        with patch.dict(os.environ, {}, clear=True):
            result = get_instance_holdover_time('ptp4l-0', 30)
        self.assertEqual(result, 45)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_instance_holdover_time_instance_not_found(self, mock_file,
                                                           mock_exists):
        """Test fallback when instance not found in config and no env var"""
        mock_exists.return_value = True
        mock_file.return_value.read_data = self.test_config_content
        mock_file.return_value.__iter__ = lambda self: iter(
            self.read_data.splitlines())
        with patch.dict(os.environ, {}, clear=True):
            result = get_instance_holdover_time('nonexistent-instance', 30)
        self.assertEqual(result, 30)

    def test_env_var_ptp_holdover_overrides_config(self):
        """Test PTP_HOLDOVER_SECONDS env var overrides config file value"""
        with patch.dict(os.environ, {'PTP_HOLDOVER_SECONDS': '99'}):
            result = get_instance_holdover_time('ptp4l-0', 30)
        self.assertEqual(result, 99)

    def test_env_var_osclock_holdover_overrides_config(self):
        """Test OS_CLOCK_HOLDOVER_SECONDS env var overrides config file value"""
        with patch.dict(os.environ, {'OS_CLOCK_HOLDOVER_SECONDS': '88'}):
            result = get_instance_osclock_holdover_time('phc2sys-0', 30)
        self.assertEqual(result, 88)

    def test_env_var_overall_holdover_overrides_config(self):
        """Test OVERALL_HOLDOVER_SECONDS env var overrides config file value"""
        with patch.dict(os.environ, {'OVERALL_HOLDOVER_SECONDS': '77'}):
            result = get_overall_holdover_time(30)
        self.assertEqual(result, 77)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_invalid_env_var_falls_back_to_config(
            self, mock_file, mock_exists):
        """Test invalid env var value falls back to config file"""
        mock_exists.return_value = True
        mock_file.return_value.read_data = self.test_config_content
        mock_file.return_value.__iter__ = lambda self: iter(
            self.read_data.splitlines())
        with patch.dict(os.environ, {'PTP_HOLDOVER_SECONDS': 'invalid'}):
            result = get_instance_holdover_time('ptp4l-0', 30)
        self.assertEqual(result, 45)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_instance_offset_threshold_major(self, mock_file, mock_exists):
        """Test reading major offset threshold"""
        mock_exists.return_value = True
        mock_file.return_value.read_data = self.test_config_content
        mock_file.return_value.__iter__ = lambda self: iter(
            self.read_data.splitlines())

        result = get_instance_offset_threshold(
            'ptp4l-0', constants.THRESHOLD_TYPE_MAJOR, 1000000)
        self.assertEqual(result, 2000000)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_instance_offset_threshold_minor(self, mock_file, mock_exists):
        """Test reading minor offset threshold"""
        mock_exists.return_value = True
        mock_file.return_value.read_data = self.test_config_content
        mock_file.return_value.__iter__ = lambda mock_self: iter(
            self.test_config_content.splitlines())

        result = get_instance_offset_threshold(
            'ptp4l-0', constants.THRESHOLD_TYPE_MINOR, 1000)
        self.assertEqual(result, 1500)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_instance_offset_threshold_invalid_type(self, mock_file,
                                                        mock_exists):
        """Test invalid threshold type returns default"""
        mock_exists.return_value = True

        result = get_instance_offset_threshold(
            'ptp4l-0', 'invalid_type', 1000)
        self.assertEqual(result, 1000)

    @patch('trackingfunctionsdk.common.helpers.instance_config_parser.'
           'constants.INSTANCE_CONFIG_PATH', '/test/config')
    @patch('os.path.exists')
    @patch('builtins.open')
    def test_parse_error_handling(self, mock_file, mock_exists):
        """Test error handling for malformed config"""
        mock_exists.return_value = True
        mock_file.side_effect = OSError("Permission denied")

        result = get_instance_holdover_time('ptp4l-0', 30)
        self.assertEqual(result, 30)

    def test_config_file_parsing_edge_cases(self):
        """Test parsing with comments, empty lines, and malformed entries.

        Verifies graceful handling of various edge cases.
        """
        edge_case_config = """
# Comment line
[ptp4l-0]
# Another comment
holdover_seconds 50

# Empty section
[empty-section]

[malformed-section]
invalid_line_without_space
holdover_seconds not_a_number
offset_threshold_major_nsec 1500000
"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(edge_case_config)
            temp_path = f.name

        try:
            with patch('trackingfunctionsdk.common.helpers.'
                       'instance_config_parser.constants.INSTANCE_CONFIG_PATH',
                       temp_path):
                # Should successfully parse valid entries
                result = _get_instance_config_value(
                    'ptp4l-0', 'holdover_seconds', 30)
                self.assertEqual(result, 50)

                # Should handle malformed entries gracefully
                result = _get_instance_config_value(
                    'malformed-section', 'holdover_seconds', 30)
                # Should return default due to parse error
                self.assertEqual(result, 30)

                # Should handle missing key
                result = _get_instance_config_value(
                    'empty-section', 'holdover_seconds', 30)
                self.assertEqual(result, 30)
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
