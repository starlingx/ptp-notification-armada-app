#
# Copyright (c) 2022-2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import configparser
import datetime
import logging
import os
import re
import socket
import subprocess
from glob import glob

from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.common.helpers import ptpsync as utils

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)

PLUGIN_STATUS_QUERY_EXEC = '/usr/sbin/pmc'


class OsClockMonitor:

    def __init__(self, phc2sys_config, init=True):
        self._state = OsClockState()
        self.last_event_time = None
        self.phc2sys_instance = None
        self.phc_interface = None
        self.ptp_device = None
        self.offset = None
        self.phc2sys_config = phc2sys_config
        self.config = None
        self.phc2sys_ha_enabled = False
        self.phc2sys_com_socket = None
        self.valid_phc_interfaces = None

        self.phc2sys_tolerance_low = constants.PHC2SYS_TOLERANCE_LOW
        self.phc2sys_tolerance_high = constants.PHC2SYS_TOLERANCE_HIGH
        self.phc2sys_tolerance_threshold = constants.PHC2SYS_TOLERANCE_THRESHOLD
        try:
            self.phc2sys_tolerance_threshold = int(os.environ.get('PHC2SYS_TOLERANCE_THRESHOLD',
                                                                  self.phc2sys_tolerance_threshold))
        except:
            LOG.error('Unable to convert PHC2SYS_TOLERANCE_THRESHOLD to integer,'
                      ' using the default.')

        self.set_phc2sys_instance()

        """Normally initialize all fields, but allow these to be skipped to
        assist with unit testing or to short-circuit values if required.
        """
        if init:
            self.parse_phc2sys_config()
            if 'global' not in self.config.keys():
                self.phc2sys_ha_enabled = False
            elif 'ha_enabled' in self.config['global'].keys() \
                    and self.config['global']['ha_enabled'] == '1':
                self.phc2sys_ha_enabled = True
                self.phc2sys_com_socket = self.config['global'].get(
                    'ha_phc2sys_com_socket', None)

            if self.phc2sys_ha_enabled is True:
                self.set_phc2sys_ha_interface_and_phc
            else:
                self.get_os_clock_time_source()
            self.set_utc_offset()
            self.get_os_clock_offset()
            self.set_os_clock_state()

    def set_phc2sys_instance(self):
        self.phc2sys_instance = self.phc2sys_config.split(
            constants.PHC2SYS_CONFIG_PATH + "phc2sys-")[1]
        self.phc2sys_instance = self.phc2sys_instance.split(".")[0]
        LOG.debug("phc2sys config file: %s" % self.phc2sys_config)
        LOG.debug("phc2sys instance name: %s" % self.phc2sys_instance)

    def parse_phc2sys_config(self):
        LOG.debug("Parsing %s" % self.phc2sys_config)
        config = configparser.ConfigParser(delimiters=' ')
        config.read(self.phc2sys_config)
        self.config = config

    def query_phc2sys_socket(self, query, unix_socket=None):
        if unix_socket:
            try:
                client_socket = socket.socket(
                    socket.AF_UNIX, socket.SOCK_STREAM)
                client_socket.connect(unix_socket)
                client_socket.send(query.encode())
                response = client_socket.recv(1024)
                response = response.decode().strip()
                if response == "None":
                    response = None
                return response
            except ConnectionRefusedError as err:
                LOG.error("Error connecting to phc2sys socket for instance %s: %s" % (
                    self.phc2sys_instance, err))
                return None
            except FileNotFoundError as err:
                LOG.error("Error connecting to phc2sys socket for instance %s: %s" % (
                    self.phc2sys_instance, err))
                return None
            finally:
                if hasattr(client_socket, 'close'):
                    client_socket.close()
        else:
            LOG.warning("No socket path supplied for instance %s" %
                        self.phc2sys_instance)
            return None

    def set_phc2sys_ha_interface_and_phc(self):
        self.valid_phc_interfaces = self.query_phc2sys_socket(
            'valid sources', self.phc2sys_com_socket)
        selected_phc_interface = self.query_phc2sys_socket(
            'clock source', self.phc2sys_com_socket)
        if str(self.valid_phc_interfaces) == 'None':
            LOG.info("No valid PHC device found for HA phc2sys selection.")
            self._state = OsClockState.Freerun
            self.phc_interface = selected_phc_interface
            self.ptp_device = None
        elif selected_phc_interface != self.phc_interface:
            LOG.info("Phc2sys source interface changed from %s to %s"
                     % (self.phc_interface, self.valid_phc_interfaces))
            self.phc_interface = selected_phc_interface

        if self.phc_interface is not None:
            self.ptp_device = self._get_interface_phc_device()

        LOG.debug("Phc2sys HA interface: %s ptp_device: %s" %
                  (self.phc_interface, self.ptp_device))

    def set_utc_offset(self, pidfile_path="/var/run/"):
        # Check command line options for offset
        utc_offset = self._get_phc2sys_command_line_option(pidfile_path, '-O')
        domain_number = None
        uds_addr = None

        # If not, check config file for uds_address and domainNumber
        # If uds_address, get utc_offset from TIME_PROPERTIES_DATA_SET using the phc2sys config
        if not utc_offset:
            utc_offset = constants.UTC_OFFSET
            utc_offset_valid = False

            if self.config.has_section(self.phc_interface) \
                    and 'ha_domainNumber' in self.config[self.phc_interface].keys():
                domain_number = self.config[self.phc_interface].get(
                    'ha_domainNumber')
                LOG.debug("set_utc_offset: ha_domainNumber is %s" %
                          domain_number)

            if self.config.has_section('global') \
                    and 'uds_address' in self.config['global'].keys():
                uds_addr = self.config['global']['uds_address']
                LOG.debug("set_utc_offset: uds_addr is %s" % uds_addr)

                if domain_number is None:
                    domain_number = self.config['global'].get(
                        'domainNumber', '0')
                    LOG.debug("set_utc_offset: domainNumber is %s" %
                              domain_number)

                #
                # sudo /usr/sbin/pmc -u -b 0 'GET TIME_PROPERTIES_DATA_SET'
                #
                data = subprocess.check_output(
                    [PLUGIN_STATUS_QUERY_EXEC, '-f', self.phc2sys_config, '-u', '-b', '0', '-d',
                     domain_number, 'GET TIME_PROPERTIES_DATA_SET']).decode()

                for line in data.split('\n'):
                    if 'currentUtcOffset ' in line:
                        utc_offset = line.split()[1]
                    if 'currentUtcOffsetValid ' in line:
                        utc_offset_valid = bool(int(line.split()[1]))

                if not utc_offset_valid:
                    utc_offset = constants.UTC_OFFSET
                    LOG.warning('currentUtcOffsetValid is %s, using the default currentUtcOffset %s'
                                % (utc_offset_valid, utc_offset))

        utc_offset_nanoseconds = abs(int(utc_offset)) * 1000000000
        self.phc2sys_tolerance_low = utc_offset_nanoseconds - \
            self.phc2sys_tolerance_threshold
        self.phc2sys_tolerance_high = utc_offset_nanoseconds + \
            self.phc2sys_tolerance_threshold
        LOG.debug('utc_offset_nanoseconds is %s, phc2sys_tolerance_threshold is %s'
                  % (utc_offset_nanoseconds, self.phc2sys_tolerance_threshold))
        LOG.info('phc2sys_tolerance_low is %s, phc2sys_tolerance_high is %s'
                 % (self.phc2sys_tolerance_low, self.phc2sys_tolerance_high))

    def get_os_clock_time_source(self, pidfile_path="/var/run/"):
        """Determine which PHC is disciplining the OS clock"""
        self.phc_interface = None
        self.phc_interface = self._get_phc2sys_command_line_option(
            pidfile_path, '-s')
        if self.phc_interface == constants.CLOCK_REALTIME:
            LOG.info("PHC2SYS is using CLOCK_REALTIME, OS Clock is not being "
                     "disciplined by a PHC")
            self.phc_interface = None
        if self.phc_interface is None:
            self.phc_interface = self._check_config_file_interface()
        if self.phc_interface is None:
            LOG.info("No PHC device found for phc2sys")
            self._state = OsClockState.Freerun
        else:
            self.ptp_device = self._get_interface_phc_device()

    def _get_phc2sys_command_line_option(self, pidfile_path, flag):
        pidfile = pidfile_path + "phc2sys-" + self.phc2sys_instance + ".pid"
        try:
            with open(pidfile, 'r') as f:
                pid = f.readline().strip()
            # Get command line params
            cmdline_file = "/host/proc/" + pid + "/cmdline"
            with open(cmdline_file, 'r') as f:
                cmdline_args = f.readline().strip()
            cmdline_args = cmdline_args.split("\x00")
        except OSError as ex:
            LOG.warning("Cannot open file. %s" % ex)
            return None

        # The option value will be at the index after the flag
        try:
            index = cmdline_args.index(flag)
        except ValueError as ex:
            LOG.debug("Flag not found in cmdline args. %s" % ex)
            return None

        value = cmdline_args[index + 1]
        LOG.debug("%s value is %s" % (flag, value))
        return value

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

        return None

    def _get_interface_phc_device(self):
        """Determine the phc device for the interface"""
        return utils.get_interface_phc_device(self.phc_interface)

    def get_os_clock_offset(self):
        """Get the os CLOCK_REALTIME offset"""

        if self.phc2sys_ha_enabled is True:
            # Refresh the HA source interface before checking offset
            self.set_phc2sys_ha_interface_and_phc()

        if self.ptp_device is None:
            # This may happen in virtualized environments
            LOG.warning("No PTP device. Defaulting offset value to 0.")
            self.offset = "0"
            return
        try:
            ptp_device_path = "/dev/" + self.ptp_device
            offset = subprocess.check_output(
                [constants.PHC_CTL_PATH, ptp_device_path, 'cmp']
            ).decode().split()[-1]
            offset = offset.strip("-ns")
            LOG.debug("PHC offset is %s" % offset)
            self.offset = offset
        except Exception as ex:
            # We have seen rare instances where the ptp device cannot be read
            # but then works fine on the next attempt. Setting the offset to 0
            # here will allow the OS clock to move to holdover. If there is a
            # real fault, it will stay in holdover and tranition to freerun but
            # if it was just a single miss, it will return to locked on the
            # next check.
            LOG.warning("Unable to read device offset for %s due to %s"
                        % (ptp_device_path, ex))
            LOG.warning("Check operation of %s. Defaulting offset value to 0."
                        % ptp_device_path)
            self.offset = "0"

    def set_os_clock_state(self):
        offset_int = int(self.offset)
        _, _, phc2sys, _ = \
            utils.check_critical_resources('', self.phc2sys_instance)
        if offset_int > self.phc2sys_tolerance_high or \
                offset_int < self.phc2sys_tolerance_low:
            LOG.warning("PHC2SYS offset is outside of tolerance")
            self._state = OsClockState.Freerun
        elif not phc2sys:
            LOG.warning("Phc2sys instance %s is not running", self.phc2sys_instance)
            self._state = OsClockState.Freerun
        else:
            LOG.info("PHC2SYS offset is within tolerance: %s", offset_int)
            self._state = OsClockState.Locked

        # Perform an extra check for HA Phc2sys to ensure we have a source interface
        if self.phc2sys_ha_enabled:
            if str(self.valid_phc_interfaces) == 'None':
                LOG.warning("No valid PHC device selected for HA phc2sys")
                self._state = OsClockState.Freerun

    def get_os_clock_state(self):
        return self._state

    def get_source_ptp_device(self):
        # PTP device that is disciplining the OS clock
        # This is also valid in case of HA source devices as
        # __publish_os_clock_status updates ptp_device.
        return self.ptp_device

    def os_clock_status(self, holdover_time, freq, sync_state, event_time):
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = None
        previous_sync_state = sync_state
        if previous_sync_state == constants.HOLDOVER_PHC_STATE:
            time_in_holdover = round(current_time - event_time)
        max_holdover_time = (holdover_time - freq * 2)

        self.set_utc_offset()
        self.get_os_clock_offset()
        self.set_os_clock_state()

        if self.get_os_clock_state() == constants.FREERUN_PHC_STATE:
            if previous_sync_state in [constants.UNKNOWN_PHC_STATE,
                                       constants.FREERUN_PHC_STATE]:
                self._state = constants.FREERUN_PHC_STATE
            elif previous_sync_state == constants.LOCKED_PHC_STATE:
                self._state = constants.HOLDOVER_PHC_STATE
            elif previous_sync_state == constants.HOLDOVER_PHC_STATE and \
                    time_in_holdover < max_holdover_time:
                LOG.info("OS Clock: Time in holdover is %s "
                          "Max time in holdover is %s"
                          % (time_in_holdover, max_holdover_time))
                self._state = constants.HOLDOVER_PHC_STATE
            else:
                self._state = constants.FREERUN_PHC_STATE

        # determine if os clock sync state has changed since the last check
        if self._state != previous_sync_state:
            new_event = True
            event_time = datetime.datetime.utcnow().timestamp()
        else:
            new_event = False
        return new_event, self.get_os_clock_state(), event_time


if __name__ == "__main__":
    # This file can be run in a ptp-notification pod to verify the
    # functionality of os_clock_monitor.
    test_monitor = OsClockMonitor()
