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
import datetime
import logging
import os
import re
import sys

from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import ptpsync as utils

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class PtpMonitor:
    _clock_class = None
    _ptp_sync_state = constants.UNKNOWN_PHC_STATE
    _new_ptp_sync_event = False
    _new_clock_class_event = False
    _ptp_event_time = None
    _clock_class_event_time = None
    _clock_class_retry = 3

    # Critical resources
    ptp4l_service_name = None
    ptp4l_config = None
    phc2sys_service_name = None

    ptp_oper_dict = {
        # [pmc cmd, ptp keywords,...]
        1: ["'GET PORT_DATA_SET'", constants.PORT_STATE],
        2: ["'GET TIME_STATUS_NP'", constants.GM_PRESENT, constants.MASTER_OFFSET],
        3: ["'GET PARENT_DATA_SET'", constants.GM_CLOCK_CLASS, constants.GRANDMASTER_IDENTITY],
        4: ["'GET TIME_PROPERTIES_DATA_SET'", constants.TIME_TRACEABLE],
        5: ["'GET DEFAULT_DATA_SET'", constants.CLOCK_IDENTITY, constants.CLOCK_CLASS],
    }

    pmc_query_results = {}

    def __init__(self, ptp4l_instance, holdover_time, freq, phc2sys_service_name, init=True):

        if init:
            self.ptp4l_config = "/ptp/ptpinstance/ptp4l-%s.conf" % ptp4l_instance
            self.ptp4l_service_name = ptp4l_instance
            self.phc2sys_service_name = phc2sys_service_name
            self.holdover_time = int(holdover_time)
            self.freq = int(freq)
            self._ptp_event_time = datetime.datetime.utcnow().timestamp()
            self._clock_class_event_time = datetime.datetime.utcnow().timestamp()
            self.set_ptp_sync_state()
            self.set_ptp_clock_class()

    def set_ptp_sync_state(self):
        new_ptp_sync_event, ptp_sync_state, ptp_event_time = self.ptp_status()
        if ptp_sync_state != self._ptp_sync_state:
            self._new_ptp_sync_event = new_ptp_sync_event
            self._ptp_sync_state = ptp_sync_state
            self._ptp_event_time = ptp_event_time
        else:
            self._new_ptp_sync_event = new_ptp_sync_event

    def get_ptp_sync_state(self):
        return self._new_ptp_sync_event, self._ptp_sync_state, self._ptp_event_time

    def set_ptp_clock_class(self):
        try:
            clock_class = self.pmc_query_results['clockClass']
            # Reset retry counter upon getting clock class
            self._clock_class_retry = 3
        except KeyError:
            LOG.warning("set_ptp_clock_class: Unable to read current clockClass")
            if self._clock_class_retry > 0:
                self._clock_class_retry -= 1
                LOG.warning("Trying to get clockClass %s more time(s) before "
                            "setting clockClass 248 (FREERUN)" % self._clock_class_retry)
                clock_class = self._clock_class
            else:
                clock_class = "248"
                self._clock_class_retry = 3
        if clock_class != self._clock_class:
            self._clock_class = clock_class
            self._new_clock_class_event = True
            self._clock_class_event_time = datetime.datetime.utcnow().timestamp()
            LOG.debug(self.pmc_query_results)
            LOG.info("PTP clock class is %s" % self._clock_class)
        else:
            self._new_clock_class_event = False

    def get_ptp_clock_class(self):
        self.set_ptp_clock_class()
        return self._new_clock_class_event, self._clock_class, self._clock_class_event_time

    def ptp_status(self):
        # holdover_time - time phc can maintain clock
        # freq - the frequency for monitoring the ptp status
        # sync_state - the current ptp state
        # event_time - the last time that ptp status was changed
        ####################################
        # event states:                    #
        #   Locked —> Holdover —> Freerun  #
        #     Holdover —> Locked           #
        #     Freerun —> Locked            #
        ####################################
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = round(current_time - self._ptp_event_time)
        previous_sync_state = self._ptp_sync_state
        # max holdover time is calculated to be in a 'safety' zone
        max_holdover_time = (self.holdover_time - self.freq * 2)

        pmc, ptp4l, phc2sys, ptp4lconf = utils.check_critical_resources(self.ptp4l_service_name,
                                                                        self.phc2sys_service_name)
        # run pmc command if preconditions met
        if pmc and ptp4l and phc2sys and ptp4lconf:
            self.pmc_query_results, total_ptp_keywords, port_count = self.ptpsync()
            sync_state = utils.check_results(self.pmc_query_results, total_ptp_keywords, port_count)
        else:
            LOG.warning("Missing critical resource: PMC %s PTP4L %s PHC2SYS %s PTP4LCONF %s" % (pmc, ptp4l, phc2sys, ptp4lconf))
            sync_state = PtpState.Freerun
        # determine if transition into holdover mode (cannot be in holdover if system clock is
        # not in
        # sync)
        if sync_state == PtpState.Freerun and phc2sys:
            if previous_sync_state in [constants.UNKNOWN_PHC_STATE, PtpState.Freerun]:
                sync_state = PtpState.Freerun
            elif previous_sync_state == PtpState.Locked:
                sync_state = PtpState.Holdover
            elif previous_sync_state == PtpState.Holdover and time_in_holdover < \
                    max_holdover_time:
                sync_state = PtpState.Holdover
            else:
                sync_state = PtpState.Freerun

        # determine if ptp sync state has changed since the last one
        LOG.debug("ptp_monitor: sync_state %s, "
                  "previous_sync_state %s" % (sync_state, previous_sync_state))
        if sync_state != previous_sync_state:
            new_event = True
            self._ptp_event_time = datetime.datetime.utcnow().timestamp()
        else:
            new_event = False
        return new_event, sync_state, self._ptp_event_time

    def ptpsync(self):
        result = {}
        total_ptp_keywords = 0
        port_count = 0

        ptp_dict_to_use = self.ptp_oper_dict
        len_dic = len(ptp_dict_to_use)

        for key in range(1, len_dic + 1):
            cmd = ptp_dict_to_use[key][0]
            cmd = "pmc -b 0 -u -f /ptp/ptpinstance/ptp4l-" + self.ptp4l_service_name + ".conf " +\
                  cmd

            ptp_keyword = ptp_dict_to_use[key][1:]
            total_ptp_keywords += len(ptp_keyword)

            out, err, errcode = utils.run_shell2('.', None, cmd)
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
                            result.update({constants.PORT.format(port_count): state[1]})
                        else:
                            state[1] = state[1].replace('\\n', '')
                            state[1] = state[1].replace('\'', '')
                            result.update({state[0]: state[1]})
        # making sure at least one port is available
        if port_count == 0:
            port_count = 1
        # adding the possible ports minus one keyword not used, "portState"
        total_ptp_keywords = total_ptp_keywords + port_count - 1
        return result, total_ptp_keywords, port_count


if __name__ == "__main__":
    test_ptp = PtpMonitor()
    LOG.debug("PTP sync state for %s is %s" % (
    test_ptp.ptp4l_service_name, test_ptp.get_ptp_sync_state()))
    LOG.debug("PTP clock class for %s is %s" % (
    test_ptp.ptp4l_service_name, test_ptp.get_ptp_clock_class()))
