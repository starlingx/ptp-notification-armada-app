"""
Test configuration and fixtures for
ptp-notification-armada-app.
"""
"""
Copyright (c) 2026 Wind River Systems, Inc.
SPDX-License-Identifier: Apache-2.0
"""
import os
import sys
import tempfile

import pytest

# Add source paths for imports
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
TRACKING_SDK = os.path.join(
    PROJECT_ROOT,
    'notificationservice-base-v2',
    'ptptrackingfunction')

if TRACKING_SDK not in sys.path:
    sys.path.insert(0, TRACKING_SDK)


@pytest.fixture
def tmp_config_dir():
    """Create a temporary directory for config files.

    Returns temporary directory path as a string.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_ptp4l_config(tmp_config_dir):
    """Create a sample ptp4l config file.

    tmp_config_dir -- temporary directory path

    Returns path to the created config file.
    """
    config_path = os.path.join(
        tmp_config_dir, 'ptp4l-test-instance.conf')
    with open(config_path, 'w') as config_file:
        config_file.write("[global]\n")
        config_file.write("domainNumber 0\n")
        config_file.write("[ens1f0]\n")
        config_file.write("[ens1f1]\n")
    return config_path


@pytest.fixture
def sample_phc2sys_config(tmp_config_dir):
    """Create a sample phc2sys config file.

    tmp_config_dir -- temporary directory path

    Returns path to the created config file.
    """
    config_path = os.path.join(
        tmp_config_dir,
        'phc2sys-test-instance.conf')
    with open(config_path, 'w') as config_file:
        config_file.write("[global]\n")
        config_file.write("domainNumber 0\n")
        config_file.write("[ens1f0]\n")
    return config_path


@pytest.fixture
def sample_ts2phc_config(tmp_config_dir):
    """Create a sample ts2phc config file.

    tmp_config_dir -- temporary directory path

    Returns path to the created config file.
    """
    config_path = os.path.join(
        tmp_config_dir,
        'ts2phc-test-instance.conf')
    with open(config_path, 'w') as config_file:
        config_file.write("[global]\n")
        config_file.write(
            "ts2phc.nmea_serialport"
            " /dev/ttyGNSS_1800_0\n")
        config_file.write("[ens1f0]\n")
    return config_path


@pytest.fixture
def sample_instance_config(tmp_config_dir):
    """Create a sample instance monitoring config.

    tmp_config_dir -- temporary directory path

    Returns path to the created config file.
    """
    config_path = os.path.join(
        tmp_config_dir,
        'instance-monitoring.conf')
    with open(config_path, 'w') as config_file:
        config_file.write("[test-instance]\n")
        config_file.write("holdover_seconds 60\n")
        config_file.write(
            "offset_threshold_major_nsec 500\n")
        config_file.write(
            "offset_threshold_minor_nsec 200\n")
        config_file.write("\n")
        config_file.write("[another-instance]\n")
        config_file.write("holdover_seconds 45\n")
    return config_path
