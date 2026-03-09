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
