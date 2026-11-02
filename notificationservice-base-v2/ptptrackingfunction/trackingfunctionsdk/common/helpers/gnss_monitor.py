#
# Copyright (c) 2022-2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import datetime
import os.path
import re

from abc import ABC, abstractmethod

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers import log_helper
from trackingfunctionsdk.common.helpers import ptpsync as utils
from trackingfunctionsdk.common.helpers.cgu_handler import CguHandler
from trackingfunctionsdk.common.helpers.cgu_handler import DeviceType
from trackingfunctionsdk.common.helpers.instance_config_parser import get_instance_holdover_time
from trackingfunctionsdk.model.dto.gnssstate import GnssState

LOG = logging.getLogger(__name__)
log_helper.config_logger(LOG)


class Observer(ABC):
    @abstractmethod
    def update(self, subject, matched_line) -> None:
        """
        Receive update from subject.
        """
        pass


class GnssMonitor(Observer):
    gnss_eec_state = ""
    gnss_pps_state = ""
    _state = GnssState()
    gnss_cgu_handler = None

    def __init__(self, config_file, nmea_serialport=None, pci_addr=None,
                 cgu_path=None, holdover_time=30):
        self.config_file = config_file
        self.ts2phc_service_name = None
        self.ts2phc_not_running_log_throttle_count = 0
        try:
            pattern = '(?<=' + \
                      constants.TS2PHC_CONFIG_PATH + \
                      'ts2phc-).*(?=.conf)'
            match = re.search(pattern, self.config_file)
            self.ts2phc_service_name = match.group()
        except AttributeError:
            LOG.warning(
                "GnssMonitor: Unable to determine tsphc_service name from %s",
                self.config_file)

        self.holdover_time = get_instance_holdover_time(
            self.ts2phc_service_name, holdover_time)
        LOG.info("GNSS Monitor initialized: instance=%s, holdover_time=%ds",
                 self.ts2phc_service_name, self.holdover_time)

        self._sync_state = GnssState.Failure_Nofix
        self._event_time = datetime.datetime.utcnow().timestamp()

        self.set_ptp_devices()
        # Setup GNSS data
        self.gnss_cgu_handler = CguHandler(config_file, nmea_serialport,
                                           pci_addr, cgu_path)
        self.gnss_cgu_handler.read_cgu()

        # Initialize status: record the GNSS reference pin's own lock status
        # on each DPLL device (present-or-standby), mirroring the pin-aware
        # view used by set_gnss_status(). This reads the GNSS pin directly so
        # a GNSS standby (SELECTABLE, e.g. GNSS secondary behind a PTP primary)
        # is still observed, not only the actively-selected master pin.
        self.gnss_cgu_handler.refresh_gnss_pins()
        self.gnss_eec_state = self.gnss_cgu_handler.get_gnss_pin_lock(
            DeviceType.EEC)
        self.gnss_pps_state = self.gnss_cgu_handler.get_gnss_pin_lock(
            DeviceType.PPS)

    def set_ptp_devices(self):
        ptp_devices = set()
        phc_interfaces = self._check_config_file_interfaces()
        for phc_interface in phc_interfaces:
            ptp_device = utils.get_interface_phc_device(phc_interface)
            if ptp_device is not None:
                ptp_devices.add(ptp_device)
        self.ptp_devices = list(ptp_devices)
        LOG.debug("TS2PHC PTP devices are %s", self.ptp_devices)

    def get_ptp_devices(self):
        return self.ptp_devices

    def _check_config_file_interfaces(self):
        phc_interfaces = []
        try:
            with open(self.config_file, 'r', encoding='utf-8') as config_file:
                config_lines = config_file.readlines()
                config_lines = [line.rstrip() for line in config_lines]
        except FileNotFoundError:
            LOG.warning("Config file not found: %s", self.config_file)
            return phc_interfaces

        for line in config_lines:
            # Find the interface value inside the square brackets
            if re.match(r"^\[.*\]$", line) and line != "[global]":
                phc_interface = line.strip("[]")
                LOG.debug("TS2PHC interface is %s", phc_interface)
                phc_interfaces.append(phc_interface)

        return phc_interfaces

    def update(self, subject, matched_line) -> None:
        LOG.info("Kernel event detected. %s", matched_line)
        self.set_gnss_status()

    def set_gnss_status(self):
        """Set GNSS Status based on CGU information"""

        # Check that ts2phc is running, else Freerun
        pid_file = f'/var/run/ts2phc-{self.ts2phc_service_name}.pid'
        if not os.path.isfile(pid_file):
            if self.ts2phc_not_running_log_throttle_count % \
                    constants.LOG_THROTTLE == 0:
                LOG.warning("TS2PHC instance %s is not running, "
                            "reporting GNSS unlocked.", self.ts2phc_service_name)
            self.ts2phc_not_running_log_throttle_count += 1
            self._state = GnssState.Failure_Nofix
            return
        else:
            self.ts2phc_not_running_log_throttle_count = 0

        self.gnss_cgu_handler.read_cgu()

        # Report GNSS SYNCHRONIZED based on the GNSS reference pin's own
        # health, not on whichever pin the DPLL has currently selected.
        #
        # The DPLL has two devices: EEC (frequency) and PPS (phase/time). When
        # a PTP 1PPS backhaul is the configured primary and GNSS is the
        # secondary, the phase/time (PPS) device selects the backhaul pin and
        # keeps the GNSS pin as a healthy standby (SELECTABLE), while the
        # frequency (EEC) device still rides GNSS (the backhaul 1PPS cannot
        # drive a frequency reference). The GNSS source as a whole is still
        # disciplined and synchronized in this state, so it must be reported
        # SYNCHRONIZED -- but the actively-selected PPS pin is the backhaul,
        # not GNSS. Keying on the selected pin therefore misreports a healthy
        # GNSS standby as FAILURE-NOFIX.
        #
        # Inspect the GNSS pin itself on each device: GNSS is synchronized when
        # its pin is present (CONNECTED or SELECTABLE) AND locked on both
        # devices. Keying on the GNSS pin's own identity also preserves the
        # guard against a SyncE recovered-clock failover: when GNSS is lost the
        # DPLL may lock to a SyncE/backhaul pin, but there is then no GNSS pin
        # present+locked, so this correctly stays FAILURE-NOFIX.
        self.gnss_cgu_handler.refresh_gnss_pins()
        eec_ok = self._gnss_pin_healthy(DeviceType.EEC)
        pps_ok = self._gnss_pin_healthy(DeviceType.PPS)
        LOG.debug("GNSS EEC healthy: %s, GNSS PPS healthy: %s",
                  eec_ok, pps_ok)
        if eec_ok and pps_ok:
            self._state = GnssState.Synchronized
        else:
            self._state = GnssState.Failure_Nofix

        LOG.debug("Set state GNSS to %s", self._state)

    def _gnss_pin_healthy(self, device_type):
        """Return True when the GNSS reference pin on a DPLL device is a
        healthy source: present (CONNECTED or SELECTABLE) and locked.

        A SELECTABLE GNSS pin is a healthy standby (e.g. GNSS secondary while
        a PTP backhaul is the active primary) and counts as synchronized. A
        GNSS pin that is DISCONNECTED, or present but not locked (acquiring /
        no fix), does NOT -- so a genuine GNSS loss still reports
        FAILURE-NOFIX.
        """
        state = self.gnss_cgu_handler.get_gnss_pin_state(device_type)
        state = getattr(state, "value", state)
        lock = self.gnss_cgu_handler.get_gnss_pin_lock(device_type)
        lock = getattr(lock, "value", lock)
        present = state in (constants.GNSS_PIN_STATE_CONNECTED,
                            constants.GNSS_PIN_STATE_SELECTABLE)
        return present and lock == constants.GNSS_LOCKED_HO_ACQ

    def is_time_source_locked(self):
        """Return True if the DPLL is locked to a valid PHASE/TIME source
        (GNSS or an external/SDP 1PPS backhaul pin), independent of whether
        that source is GNSS specifically.

        Used by the overall sync-state aggregation: after a dpll-mgr failover
        GNSS -> PTP-backhaul (SDP0, pin_type=ext) the DPLL stays locked (it
        just switches pins), so the overall timing is still healthy even
        though the GNSS per-source view (pin-aware) correctly reports GNSS
        lost. SyncE (synce-eth-port, frequency-only), MUX and the internal
        oscillator do NOT count -- they cannot keep the overall state Locked.
        This is distinct from get_gnss_status(), which is GNSS-pin-specific.

        The required device-lock depends on the active phase/time (PPS) pin
        type:
          - GNSS pin : EEC and PPS both locked. A GNSS/PRTC source disciplines
            both frequency (EEC) and phase/time (PPS); if the EEC is not locked
            to GNSS, GNSS is not genuinely healthy.
          - external pin (PTP backhaul SDP0): PPS locked. The EEC is expected
            to remain in holdover on the backhaul, so only the phase/time (PPS)
            lock to the backhaul 1PPS is required.
          - any other pin type: not a valid phase/time source -> False (this
            method simply does not contribute; the overall state is then
            decided by the other aggregation branches, unchanged).

        Reads the CGU directly (fresh read_cgu + accessors) rather than the
        cached gnss_eec_state/gnss_pps_state: set_gnss_status() only records
        those cached values when the active pin is GNSS, and CguHandler filters
        its pin set to CONNECTED + INPUT so the accessors return the ACTIVE
        input pin's status and type.
        """
        self.gnss_cgu_handler.read_cgu()
        pps_type = self.gnss_cgu_handler.get_pps_pin_type()
        pps_type = getattr(pps_type, "value", pps_type)
        pps_status = self.gnss_cgu_handler.get_pps_status()
        if pps_type == constants.PIN_TYPE_GNSS:
            eec_status = self.gnss_cgu_handler.get_eec_status()
            return (eec_status == constants.GNSS_LOCKED_HO_ACQ
                    and pps_status == constants.GNSS_LOCKED_HO_ACQ)
        if pps_type == constants.PIN_TYPE_EXT:
            return pps_status == constants.GNSS_LOCKED_HO_ACQ
        return False

    def get_gnss_status(
            self,
            sync_state=None,
            event_time=None):
        """Return GNSS status and determine if GNSS state has changed

        Parameters are deprecated and maintained for backward compatibility.
        The method now manages state internally.
        """
        if sync_state is not None:
            self._sync_state = sync_state
        if event_time is not None:
            self._event_time = event_time

        previous_sync_state = self._sync_state
        current_time = datetime.datetime.utcnow().timestamp()
        time_in_holdover = None
        if previous_sync_state == GnssState.Holdover:
            time_in_holdover = round(current_time - self._event_time)

        self.set_gnss_status()

        if self._state != GnssState.Synchronized:
            if previous_sync_state == GnssState.Synchronized:
                self._state = GnssState.Holdover
                LOG.info(
                    "GNSS Holdover: Transitioning SYNCHRONIZED -> HOLDOVER "
                    "(holdover_time=%ds)", self.holdover_time)
            elif (previous_sync_state == GnssState.Holdover and
                    time_in_holdover < self.holdover_time):
                LOG.debug(
                    "GNSS Holdover: Remaining in HOLDOVER "
                    "(%ds/%ds elapsed, %ds remaining)",
                    time_in_holdover, self.holdover_time,
                    self.holdover_time - time_in_holdover)
                self._state = GnssState.Holdover
            else:
                self._state = GnssState.Failure_Nofix
                if previous_sync_state == GnssState.Holdover:
                    LOG.warning(
                        "GNSS Holdover: Transitioning HOLDOVER -> "
                        "FAILURE_NOFIX (holdover expired: %ds >= %ds)",
                        time_in_holdover, self.holdover_time)
                else:
                    LOG.debug(
                        "GNSS Holdover: Remaining in FAILURE_NOFIX state "
                        "(previous: %s)", previous_sync_state)

        if self._state != previous_sync_state:
            new_event = True
            self._event_time = (datetime.datetime.now(datetime.timezone.utc)
                                .timestamp())
        else:
            new_event = False

        self._sync_state = self._state
        return new_event, self._state, self._event_time
