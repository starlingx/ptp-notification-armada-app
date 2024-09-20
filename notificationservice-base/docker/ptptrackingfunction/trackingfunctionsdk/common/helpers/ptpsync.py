#! /usr/bin/python3
#
# Copyright (c) 2021-2023 Wind River Systems, Inc.
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
import errno, os
import os.path
import socket
import sys
import subprocess
import datetime
import logging
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper


LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)



# dictionary includes PMC commands used and keywords of intrest
ptp_oper_dict = {
    #[pmc cmd, ptp keywords,...]
    1: ["'GET PORT_DATA_SET'", constants.PORT_STATE],
    2: ["'GET TIME_STATUS_NP'", constants.GM_PRESENT, constants.MASTER_OFFSET],
    3: ["'GET PARENT_DATA_SET'", constants.GM_CLOCK_CLASS, constants.GRANDMASTER_IDENTITY],
    4: ["'GET TIME_PROPERTIES_DATA_SET'", constants.TIME_TRACEABLE],
    5: ["'GET DEFAULT_DATA_SET'", constants.CLOCK_IDENTITY]
}

ptp4l_service_name = os.environ.get('PTP4L_SERVICE_NAME', 'ptp4l')
phc2sys_service_name = os.environ.get('PHC2SYS_SERVICE_NAME', 'phc2sys')
phc2sys_com_socket = os.environ.get('PHC2SYS_COM_SOCKET', "false")
phc2sys_config_file_path = '%sphc2sys-%s.conf' % (constants.LINUXPTP_CONFIG_PATH,
                                                  phc2sys_service_name)

ptp4l_clock_class_locked = constants.CLOCK_CLASS_LOCKED_LIST
try:
    tmp = os.environ.get('PTP4L_CLOCK_CLASS_LOCKED_LIST', ','.join(ptp4l_clock_class_locked))
    ptp4l_clock_class_locked = sorted([str(int(e)) for e in tmp.split(',')])
except:
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

def check_critical_resources():
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
    if os.path.isfile('%sptp4l-%s.conf' % (constants.LINUXPTP_CONFIG_PATH, ptp4l_service_name)):
        ptp4lconf = True
    if phc2sys_com_socket != "false":
        # User enabled phc2sys HA source clock validation
        phc2sys_source_clock = check_phc2sys_ha_source()
        if phc2sys_source_clock is None:
            # Log that phc2sys has no sources, but allow state checking to proceed
            LOG.info("HA phc2sys has no valid sources to select")
        else:
            LOG.debug("HA phc2sys has valid sources: %s" % phc2sys_source_clock)
    return pmc, ptp4l, phc2sys, ptp4lconf

def check_phc2sys_ha_source():
    query = 'valid sources'
    try:
        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(phc2sys_com_socket)
        client_socket.send(query.encode())
        response = client_socket.recv(1024)
        response = response.decode().strip()
        if str(response) == "None":
            response = None
        return response
    except ConnectionRefusedError as err:
        LOG.error("Error connecting to phc2sys socket for instance %s: %s" % (
            phc2sys_service_name, err))
        return None
    except FileNotFoundError as err:
        LOG.error("Error connecting to phc2sys socket for instance %s: %s" % (
            phc2sys_service_name, err))
        return None
    finally:
        if hasattr(client_socket, 'close'):
            client_socket.close()

def check_results(result, total_ptp_keywords, port_count):
    # sync state is in 'Locked' state and will be overwritten if
    # it is not the case
    sync_state = constants.LOCKED_PHC_STATE

    local_gm = False

    # check for a healthy result
    if len(result) != total_ptp_keywords:
        LOG.info("Results %s" % result)
        LOG.info("Results len %s, total_ptp_keywords %s" % (len(result), total_ptp_keywords))
        raise RuntimeError("PMC results are incomplete, retrying")
    # determine the current sync state
    if (result[constants.GM_PRESENT].lower() != constants.GM_IS_PRESENT
            and result[constants.GRANDMASTER_IDENTITY] != result[constants.CLOCK_IDENTITY]):
        sync_state = constants.FREERUN_PHC_STATE
    elif result[constants.GRANDMASTER_IDENTITY] == result[constants.CLOCK_IDENTITY]:
        local_gm = True
        LOG.debug("Local node is a GM")
    if not local_gm:
        for port in range(1, port_count + 1):
            if result[constants.PORT.format(port)].lower() == constants.SLAVE_MODE:
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
    return sync_state

def ptpsync():
    result = {}
    total_ptp_keywords = 0
    port_count = 0

    ptp_dict_to_use = ptp_oper_dict
    len_dic = len(ptp_dict_to_use)

    for key in range(1,len_dic+1):
        cmd = ptp_dict_to_use[key][0]
        cmd = "pmc -b 0 -u -f " + constants.LINUXPTP_CONFIG_PATH + "ptp4l-" + ptp4l_service_name + ".conf " + cmd

        ptp_keyword = ptp_dict_to_use[key][1:]
        total_ptp_keywords += len(ptp_keyword)

        out, err, errcode = run_shell2('.', None, cmd)
        if errcode != 0:
            LOG.warning('pmc command returned unknown result')
            sys.exit(0)
        out = str(out)
        try:
            out = out.split("\\n\\t\\t")
        except:
            LOG.warning('cannot split "out" into a list')
            sys.exit(0)
        for state in out:
            try:
                state = state.split()
            except:
                LOG.warning('cannot split "state" into a list')
                sys.exit(0)
            if len(state) <= 1:
                LOG.warning('not received the expected list length')
                sys.exit(0)
            for item in ptp_keyword:
                 if state[0] == item:
                     if item == constants.PORT_STATE:
                         port_count += 1
                         result.update({constants.PORT.format(port_count):state[1]})
                     else:
                         state[1] = state[1].replace('\\n','')
                         state[1] = state[1].replace('\'','')
                         result.update({state[0]:state[1]})
    # making sure at least one port is available
    if port_count == 0:
        port_count = 1
    # adding the possible ports minus one keyword not used, "portState"
    total_ptp_keywords = total_ptp_keywords + port_count - 1
    return result, total_ptp_keywords, port_count

def ptp_status(holdover_time, freq, sync_state, event_time):
    result = {}
    # holdover_time - time phc can maintain clock
    # freq - the frequently for monitoring the ptp status
    # sync_state - the current ptp state
    # event_time - the last time that ptp status was changed
    ####################################
    # event states:                    #
    #   Locked —> Holdover —> Freerun  #
    #     Holdover —> Locked           #
    #     Freerun —> Locked            #
    ####################################
    current_time = datetime.datetime.now().timestamp()
    time_in_holdover = round(current_time - event_time)
    previous_sync_state = sync_state
    # max holdover time is calculated to be in a 'safety' zoon
    max_holdover_time = (holdover_time - freq * 2)

    pmc, ptp4l, phc2sys, ptp4lconf = check_critical_resources()
    # run pmc command if preconditions met
    if pmc and ptp4l and phc2sys and ptp4lconf:
        result, total_ptp_keywords, port_count = ptpsync()
        try:
            sync_state = check_results(result, total_ptp_keywords, port_count)
        except RuntimeError as err:
            LOG.warning(err)
            sync_state = previous_sync_state
    else:
        LOG.warning("Critical resources not available: pmc %s ptp4l %s phc2sys %s ptp4lconf %s" %
                    (pmc, ptp4l, phc2sys, ptp4lconf))
        sync_state = constants.FREERUN_PHC_STATE
    # determine if transition into holdover mode (cannot be in holdover if system clock is not in sync)
    if sync_state == constants.FREERUN_PHC_STATE and phc2sys:
        if previous_sync_state in [constants.UNKNOWN_PHC_STATE, constants.FREERUN_PHC_STATE]:
            sync_state = constants.FREERUN_PHC_STATE
        elif previous_sync_state == constants.LOCKED_PHC_STATE:
            sync_state = constants.HOLDOVER_PHC_STATE
        elif previous_sync_state == constants.HOLDOVER_PHC_STATE and time_in_holdover < max_holdover_time:
            sync_state = constants.HOLDOVER_PHC_STATE
        else:
            sync_state == constants.FREERUN_PHC_STATE

    # determine if ptp sync state has changed since the last one
    if sync_state != previous_sync_state:
        new_event = "true"
        event_time = datetime.datetime.now().timestamp()
    else:
        new_event = "false"
    return new_event, sync_state, event_time
