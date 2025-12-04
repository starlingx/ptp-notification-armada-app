#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""
PTP Instance Configuration Parser

This module provides utilities to parse instance-specific configuration values
for PTP (Precision Time Protocol) tracking functions. It allows different PTP
instances to have customized settings by reading from a configuration file.

The configuration file format follows INI-style sections:
    [instance_name]
    holdover_seconds 60
    offset_threshold_major_nsec 100
    offset_threshold_minor_nsec 50

Usage:
    # Get holdover time for a specific instance
    holdover = get_instance_holdover_time('ts2phc-instance1', 30)

    # Get offset thresholds
    major_threshold = get_instance_offset_threshold(
        'ts2phc-instance1', 'major', 100)
    minor_threshold = get_instance_offset_threshold(
        'ts2phc-instance1', 'minor', 50)

Functions:
    get_instance_holdover_time: Get holdover time for specific PTP instance
    get_instance_offset_threshold: Get offset threshold for specific instance
"""

import logging
import os
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


def get_instance_holdover_time(instance_name, default_holdover=constants.DEFAULT_HOLDOVER_SECONDS):
    """Get holdover time for specific PTP instance from config file"""
    return _get_instance_config_value(instance_name,
                                      constants.HOLDOVER_SECONDS_KEY,
                                      default_holdover)


def get_instance_offset_threshold(instance_name, threshold_type, default_threshold):
    """Get offset threshold for specific instance from config file"""
    threshold_keys = {
        constants.THRESHOLD_TYPE_MAJOR: constants.OFFSET_THRESHOLD_MAJOR_KEY,
        constants.THRESHOLD_TYPE_MINOR: constants.OFFSET_THRESHOLD_MINOR_KEY
    }

    key = threshold_keys.get(threshold_type)
    if not key:
        LOG.error("Unknown threshold type: %s", threshold_type)
        return default_threshold

    return _get_instance_config_value(instance_name, key, default_threshold)


def _get_instance_config_value(instance_name, key, default_value):
    """Get a specific config value for an instance"""

    if not os.path.exists(constants.INSTANCE_CONFIG_PATH):
        LOG.warning("Instance config file not found: %s, using default %s=%s",
                    constants.INSTANCE_CONFIG_PATH, key, default_value)
        return default_value

    try:
        current_section = None
        with open(constants.INSTANCE_CONFIG_PATH, 'r', encoding='utf-8') as config_file:
            for line in config_file:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Parse section headers
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    continue

                # Parse key-value pairs in the target section
                if current_section == instance_name and line.startswith(key + ' '):
                    parts = line.split()
                    if len(parts) >= 2:
                        value = int(parts[1])
                        LOG.info("Instance %s: Using %s=%s from config",
                                 instance_name, key, value)
                        return value

        LOG.warning("Instance %s or %s not found in config, using default %s",
                    instance_name, key, default_value)
        return default_value

    except (ValueError, IndexError) as parse_error:
        LOG.error("Error parsing config value for %s.%s: %s, using default %s",
                  instance_name, key, parse_error, default_value)
        return default_value
    except OSError as file_error:
        LOG.error("Error reading instance config: %s, using default %s=%s",
                  file_error, key, default_value)
        return default_value
