#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import datetime
import logging
import os
import subprocess
import re
from glob import glob

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.osclockstate import OsClockState

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class OsClockMonitor:
    _state = OsClockState()
    last_event_time = None
    phc2sys_instance = None
    phc2sys_config = None
    phc_interface = None
    ptp_device = None
    offset = None

    def __init__(self, init=True):
        self.phc2sys_config = os.environ.get("PHC2SYS_CONFIG", constants.PHC2SYS_DEFAULT_CONFIG)
        self.set_phc2sys_instance()

        """Normally initialize all fields, but allow these to be skipped to assist with unit testing
        or to short-circuit values if required.
        """
        if init:
            self.get_os_clock_time_source()
            self.get_os_clock_offset()
            self.set_os_clock_state()

    def set_phc2sys_instance(self):
        self.phc2sys_instance = self.phc2sys_config.split(constants.PHC2SYS_CONF_PATH
                                                          + "phc2sys-")[1]
        self.phc2sys_instance = self.phc2sys_instance.split(".")[0]
        LOG.debug("phc2sys config file: %s" % self.phc2sys_config)
        LOG.debug("phc2sys instance name: %s" % self.phc2sys_instance)

    def get_os_clock_time_source(self, pidfile_path="/var/run/"):
        """Determine which PHC is disciplining the OS clock"""
        self.phc_interface = None
        self.phc_interface = self._check_command_line_interface(pidfile_path)
        if self.phc_interface is None:
            self.phc_interface = self._check_config_file_interface()
        if self.phc_interface is None:
            LOG.info("No PHC device found for phc2sys, status is FREERUN.")
            self._state = OsClockState.Freerun
        else:
            self.ptp_device = self._get_interface_phc_device()

    def _check_command_line_interface(self, pidfile_path):
        pidfile = pidfile_path + "phc2sys-" + self.phc2sys_instance + ".pid"
        with open(pidfile, 'r') as f:
            pid = f.readline().strip()
        # Get command line params
        cmdline_file = "/host/proc/" + pid + "/cmdline"
        with open(cmdline_file, 'r') as f:
            cmdline_args = f.readline().strip()
        cmdline_args = cmdline_args.split("\x00")

        # The interface will be at the index after "-s"
        try:
            interface_index = cmdline_args.index('-s')
        except ValueError as ex:
            LOG.error("No interface found in cmdline args. %s" % ex)
            return None

        phc_interface = cmdline_args[interface_index + 1]
        if phc_interface == constants.CLOCK_REALTIME:
            LOG.info("PHC2SYS is using CLOCK_REALTIME, OS Clock is not being disciplined by a PHC")
            return None
        LOG.debug("PHC interface is %s" % phc_interface)
        return phc_interface

    def _check_config_file_interface(self):
        with open(self.phc2sys_config, 'r') as f:
            config_lines = f.readlines()
            config_lines = [line.rstrip() for line in config_lines]

        for line in config_lines:
            # Find the interface value inside the square brackets
            if re.match(r"^\[.*\]$", line) and line != "[global]":
                phc_interface = line.strip("[]")

        LOG.debug("PHC interface is %s" % phc_interface)
        return phc_interface

    def _get_interface_phc_device(self):
        """Determine the phc device for the interface"""
        pattern = "/hostsys/class/net/" + self.phc_interface + "/device/ptp/*"
        ptp_device = glob(pattern)
        if len(ptp_device) == 0:
            LOG.error("No ptp device found at %s" % pattern)
            return None
        if len(ptp_device) > 1:
            LOG.error("More than one ptp device found at %s" % pattern)
            return None

        ptp_device = os.path.basename(ptp_device[0])
        LOG.debug("Found ptp device %s at %s" % (ptp_device, pattern))
        return ptp_device

    def get_os_clock_offset(self):
        """Get the os CLOCK_REALTIME offset"""
        ptp_device_path = "/dev/" + self.ptp_device
        offset = subprocess.check_output([constants.PHC_CTL_PATH, ptp_device_path, 'cmp']
                                         ).decode().split()[-1]
        offset = offset.strip("-ns")
        LOG.debug("PHC offset is %s" % offset)
        self.offset = offset

    def set_os_clock_state(self):
        offset_int = int(self.offset)
        if offset_int > constants.PHC2SYS_TOLERANCE_HIGH or \
                offset_int < constants.PHC2SYS_TOLERANCE_LOW:
            LOG.warning("PHC2SYS offset is outside of tolerance, handling state change.")
            # TODO Implement handler for os clock state change
            pass
        else:
            LOG.info("PHC2SYS offset is within tolerance, OS clock state is LOCKED")
            self._state = OsClockState.Locked

    def get_os_clock_state(self):
        return self._state


if __name__ == "__main__":
    # This file can be run in a ptp-notification pod to verify the functionality of
    # os_clock_monitor.
    test_monitor = OsClockMonitor()
