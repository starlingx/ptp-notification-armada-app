#! /usr/bin/python3
#
# Copyright (c) 2021-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

#
# This script provides the PTP synchronization status
# for PTP NIC configured as subordinate (slave mode)
# It relies on Linux ptp4l (PMC) module in order to work
# Sync status provided as: 'Locked', 'Holdover', 'Freerun'
#
#
import configparser
import os
import re
import subprocess
import logging
import time
from glob import glob
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


ptp4l_clock_class_locked = constants.CLOCK_CLASS_LOCKED_LIST
try:
    tmp = os.environ.get('PTP4L_CLOCK_CLASS_LOCKED_LIST',
                         ','.join(ptp4l_clock_class_locked))
    ptp4l_clock_class_locked = sorted([str(int(e)) for e in tmp.split(',')])
except (ValueError, TypeError):
    LOG.error('Unable to convert PTP4L_CLOCK_CLASS_LOCKED_LIST to a list of integers,'
              ' using the default.')


# run subprocess and returns out, err, errcode
def run_shell2(dir, ctx, args):
    cwd = os.getcwd()
    os.chdir(dir)

    process = subprocess.Popen(args, shell=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate()
    errcode = process.returncode

    os.chdir(cwd)

    return out, err, errcode


def check_critical_resources(ptp4l_service_name, phc2sys_service_name):
    pmc = False
    ptp4l = False
    phc2sys = False
    ptp4lconf = False

    if os.path.isfile('/usr/sbin/pmc'):
        pmc = True
    if os.path.isfile(f'/var/run/ptp4l-{ptp4l_service_name}.pid'):
        ptp4l = True
    if os.path.isfile(f'/var/run/phc2sys-{phc2sys_service_name}.pid'):
        phc2sys = True
    if os.path.isfile(constants.PTP_CONFIG_PATH +
                      f'ptp4l-{ptp4l_service_name}.conf'):
        ptp4lconf = True
    return pmc, ptp4l, phc2sys, ptp4lconf


def check_results(result, total_ptp_keywords, port_count, offset_threshold=None):
    # sync state is in 'Locked' state and will be overwritten if
    # it is not the case
    sync_state = constants.LOCKED_PHC_STATE
    # sync source is in 'NA' and will be overwritten when source
    # found to be GNSS or PTP.
    sync_source = constants.ClockSourceType.TypeNA

    local_gm = False

    # check for a healthy result
    if len(result) != total_ptp_keywords:
        LOG.info("Results %s", result)
        LOG.info("Results len %s, total_ptp_keywords %s",
                 len(result), total_ptp_keywords)
        raise RuntimeError("PMC results are incomplete, retrying")
    # determine the current sync state and sync source
    if (result[constants.GM_PRESENT].lower() != constants.GM_IS_PRESENT
            and result[constants.GRANDMASTER_IDENTITY] != result[constants.CLOCK_IDENTITY]):
        sync_state = constants.FREERUN_PHC_STATE
    elif result[constants.GRANDMASTER_IDENTITY] == result[constants.CLOCK_IDENTITY]:
        local_gm = True
        sync_source = constants.ClockSourceType.TypeGNSS
        LOG.debug("Local node is a GM")
    if not local_gm:
        for port in range(1, port_count + 1):
            if result[constants.PORT.format(port)].lower() == constants.SLAVE_MODE:
                sync_source = constants.ClockSourceType.TypePTP
                break
        else:
            sync_state = constants.FREERUN_PHC_STATE

    # We can only expect timeTraceable=1 to be set when the clockClass list is the default.
    # If the user has elected to override the Locked clockClasses, then it is necessary
    # to ignore the timeTraceable property and define the lock state based only on the
    # configured clockClasses.
    if (ptp4l_clock_class_locked == constants.CLOCK_CLASS_LOCKED_LIST
            and result[constants.TIME_TRACEABLE] != constants.TIME_IS_TRACEABLE1
            and result[constants.TIME_TRACEABLE].lower != constants.TIME_IS_TRACEABLE2):
        sync_state = constants.FREERUN_PHC_STATE
    if (result[constants.GM_CLOCK_CLASS] not in ptp4l_clock_class_locked):
        sync_state = constants.FREERUN_PHC_STATE

    # Check master offset if threshold provided and offset available
    if offset_threshold and constants.MASTER_OFFSET in result:
        try:
            master_offset = abs(int(result[constants.MASTER_OFFSET]))
            if master_offset > offset_threshold:
                LOG.warning(
                    f"PTP master offset {master_offset}ns exceeds threshold {offset_threshold}ns")
                sync_state = constants.FREERUN_PHC_STATE
        except (ValueError, TypeError):
            LOG.warning("Unable to parse master_offset value")

    return sync_state, sync_source


def parse_resource_address(resource_address):
    # The format of resource address is:
    # /{clusterName}/{siteName}(/optional/hierarchy/..)/{nodeName}/{resource}
    # Assume no optional hierarchy for now
    clusterName = resource_address.split('/')[1]
    nodeName = resource_address.split('/')[2]
    resource_path = '/' + re.split('[/]', resource_address, 3)[3]
    return clusterName, nodeName, resource_path


def format_resource_address(node_name, resource, instance=None):
    """Return a formatted resource address"""
    resource_address = '/./' + node_name
    if instance:
        resource_address = resource_address + '/' + instance + resource
    else:
        resource_address = resource_address + resource
    LOG.debug("format_resource_address %s", resource_address)
    return resource_address


def get_phc_index(phc_interface):
    """Determine the phc index"""
    phc_index = ''
    filepath = f"{constants.PTP_CONFIG_PATH}ptp-interfaces.conf"
    config = configparser.ConfigParser(delimiters=' ')
    try:
        config.read(filepath)
        if config.has_section(phc_interface):
            phc_index = config[phc_interface].get('phc_index', '')
    except(FileNotFoundError, PermissionError) as err:
        LOG.error(f"Failed to get phc index, reason: {err}")
    return phc_index


def get_interface_phc_device(phc_interface):
    """Determine the phc device for the interface"""
    phc_index = get_phc_index(phc_interface)
    LOG.debug(f"Interface {phc_interface} has phc index {phc_index}")
    if phc_index != '':
        iface_pattern = '*'
        ptp_device_pattern = f"ptp{phc_index}"
    else:
        # Use interface name as fallback solution
        # if phc index is not found.
        iface_pattern = phc_interface[:-1]+'*'
        ptp_device_pattern = '*'
    pattern = constants.PHC_PATH.format(
        iface_pattern,
        ptp_device_pattern
    )
    ptp_devices = glob(pattern)
    if len(ptp_devices) == 0:
        LOG.info("No ptp device found at %s", pattern)
    elif len(ptp_devices) > 1:
        LOG.error("More than one ptp device found at %s", pattern)
    else:
        ptp_device = os.path.basename(ptp_devices[0])
        LOG.debug("Found ptp device %s at %s", ptp_device, pattern)
        return ptp_device
    return None


def get_ts2phc_leapfile():
    """Get the leapfile path from the ts2phc configuration file.

    Searches TS2PHC_CONFIG_PATH for files matching 'ts2ph*.conf',
    reads the first match line by line, and returns the value
    associated with the 'leapfile' key.

    Returns:
        str : The leapfile path.
    """
    config_path = constants.TS2PHC_CONFIG_PATH
    search_pattern = os.path.join(config_path, "ts2ph*.conf")
    LOG.debug("Searching for ts2phc config files: %s", search_pattern)

    config_files = glob(search_pattern)
    default_file_path = os.path.normpath(constants.LEAP_FILE_PATH)

    if not config_files:
        LOG.warning("No ts2phc config files found matching pattern: %s",
                    search_pattern)
        return default_file_path

    ts2phc_config_file = config_files[0]
    LOG.debug("Using ts2phc config file: %s", ts2phc_config_file)

    try:
        with open(ts2phc_config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                elements = line.split()
                if len(elements) >= 2 and elements[0] == 'leapfile':
                    leapfile = os.path.normpath(elements[1])
                    LOG.debug("Found leapfile entry: %s", leapfile)
                    return leapfile
    except FileNotFoundError:
        LOG.warning("ts2phc config file not found: %s",
                    ts2phc_config_file)
        return default_file_path
    except OSError as ex:
        LOG.warning("Unable to read ts2phc config file %s: %s",
                    ts2phc_config_file, ex)
        return default_file_path

    LOG.warning("No 'leapfile' entry found in %s", ts2phc_config_file)
    return default_file_path


def get_latest_offset_from_leapfile(filepath):
    """Parse a leap-seconds.list file and return the latest TAI-UTC offset.

    The leap-seconds.list file contains data lines with the format:
        <NTP_timestamp>  <TAI-UTC_offset>  # <date_comment>

    The file is read once during initialization. If an operator deploys a
    new leapfile before a scheduled leap second, the entry is correctly
    ignored (future timestamp). Once the leap second occurs and the
    timestamp becomes valid, the service must be restarted to pick up the
    new value.

    Args:
        filepath: Path to the leap-seconds.list file.

    Returns:
        int or None: The TAI-UTC offset from the entry with the highest
        valid NTP timestamp, or None if the file cannot be parsed.
    """
    latest_offset = None
    now_ntp = int(time.time()) + constants.NTP_EPOCH_OFFSET
    LOG.debug("Parsing leap seconds file: %s (current NTP time: %d)",
              filepath, now_ntp)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip blank lines, comment lines, and special markers
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        timestamp = int(parts[0])
                        offset = int(parts[1])
                        if timestamp <= now_ntp:
                            latest_offset = offset
                    except ValueError:
                        continue
    except FileNotFoundError:
        LOG.warning("Leap seconds file not found: %s", filepath)
        return None
    except OSError as ex:
        LOG.warning("Unable to read leap seconds file %s: %s",
                    filepath, ex)
        return None

    if latest_offset is not None:
        LOG.debug("Latest TAI-UTC offset from leapfile: %d",
                  latest_offset)
    else:
        LOG.warning("No valid TAI-UTC offset found in %s", filepath)
    return latest_offset
