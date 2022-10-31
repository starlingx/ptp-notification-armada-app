#! /usr/bin/python3
#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
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
import os
import re
import subprocess
import logging
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


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
    if os.path.isfile('/var/run/ptp4l-%s.pid' % ptp4l_service_name):
        ptp4l = True
    if os.path.isfile('/var/run/phc2sys-%s.pid' % phc2sys_service_name):
        phc2sys = True
    if os.path.isfile(constants.PTP_CONFIG_PATH +
                      ('ptp4l-%s.conf' % ptp4l_service_name)):
        ptp4lconf = True
    return pmc, ptp4l, phc2sys, ptp4lconf


def check_results(result, total_ptp_keywords, port_count):
    # sync state is in 'Locked' state and will be overwritten if
    # it is not the case
    sync_state = constants.LOCKED_PHC_STATE

    local_gm = False

    # check for a healthy result
    if len(result) != total_ptp_keywords:
        sync_state = constants.FREERUN_PHC_STATE
        LOG.warning('results are not complete, returning FREERUN')
        return sync_state
    # determine the current sync state
    if (result[constants.GM_PRESENT].lower() != constants.GM_IS_PRESENT
            and result[constants.GRANDMASTER_IDENTITY] != result[constants.CLOCK_IDENTITY]):
        sync_state = constants.FREERUN_PHC_STATE
    elif result[constants.GRANDMASTER_IDENTITY] == result[constants.CLOCK_IDENTITY]:
        local_gm = True
        LOG.debug("Local node is a GM")
    for port in range(1, port_count + 1):
        if result[constants.PORT.format(port)].lower() == constants.SLAVE_MODE:
            break
        elif local_gm and result[constants.PORT.format(port)].lower() == constants.MASTER_MODE:
            break
    else:
        sync_state = constants.FREERUN_PHC_STATE
    if (result[constants.TIME_TRACEABLE] != constants.TIME_IS_TRACEABLE1
            and result[constants.TIME_TRACEABLE].lower != constants.TIME_IS_TRACEABLE2):
        sync_state = constants.FREERUN_PHC_STATE
    if (result[constants.GM_CLOCK_CLASS] not in
            [constants.CLOCK_CLASS_VALUE6]):
        sync_state = constants.FREERUN_PHC_STATE
    return sync_state


def parse_resource_address(resource_address):
    # The format of resource address is:
    # /{clusterName}/{siteName}(/optional/hierarchy/..)/{nodeName}/{resource}
    # Assume no optional hierarchy for now
    clusterName = resource_address.split('/')[1]
    nodeName = resource_address.split('/')[2]
    resource_path = '/' + re.split('[/]', resource_address, 3)[3]
    return clusterName, nodeName, resource_path


def format_resource_address(node_name, resource):
    # Return a resource_address
    resource_address = '/./' + node_name + resource
    return resource_address
