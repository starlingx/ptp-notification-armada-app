#
# Copyright (c) 2026 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
"""SyncE monitor — polls kernel DPLL via pynetlink for EEC lock state."""

import configparser
import datetime
import logging

from trackingfunctionsdk.common.helpers import constants

from pynetlink import NetlinkDPLL
from pynetlink import DeviceType
from pynetlink import LockStatus


LOG = logging.getLogger(__name__)


class SynceState:
    Locked = "Locked"
    Holdover = "Holdover"
    Freerun = "Freerun"
    Unknown = "Unknown"


class SynceMonitor:
    """Polls DPLL EEC lock status and reports O-RAN synce-status/lock-state."""

    def __init__(self, synce4l_instance, holdover_time=30,
                 locked_ql=None, holdover_ql=None, freerun_ql=None):
        self.synce4l_service_name = synce4l_instance
        self.holdover_time = holdover_time
        self._dpll = None
        self._clock_id = self._parse_clock_id(synce4l_instance)
        # T-GM defaults. T-BC should source QL from synce4l ESMC
        # (follow-on story).
        monitoring = self._parse_monitoring_config(synce4l_instance)
        self._locked_ql = (locked_ql if locked_ql is not None
                           else monitoring.get('static_ql', 0x02))
        self._holdover_ql = (holdover_ql if holdover_ql is not None
                             else monitoring.get('holdover_ql', 0x04))
        self._freerun_ql = (freerun_ql if freerun_ql is not None
                            else monitoring.get('freerun_ql', 0x0f))
        self._sync_state = SynceState.Unknown
        self._event_time = datetime.datetime.now(
            datetime.timezone.utc).timestamp()
        self._holdover_start = None
        self._last_ql = None
        self._ql_event_time = datetime.datetime.now(
            datetime.timezone.utc).timestamp()
        LOG.info("SyncE Monitor initialized: instance=%s, holdover_time=%ds, "
                 "clock_id=%s, ql=[locked=0x%02x, holdover=0x%02x, "
                 "freerun=0x%02x]",
                 synce4l_instance, holdover_time, self._clock_id,
                 self._locked_ql, self._holdover_ql, self._freerun_ql)

    def _parse_clock_id(self, instance_name):
        """Parse clock_id from synce4l config device section [<instance>]."""
        config_path = (f"{constants.PTP_CONFIG_PATH}"
                       f"synce4l-{instance_name}.conf")
        try:
            config = configparser.ConfigParser(delimiters=' ')
            config.read(config_path)
            device_section = f'<{instance_name}>'
            if config.has_option(device_section, 'clock_id'):
                clock_id = int(config[device_section]['clock_id'])
                LOG.info("SynceMonitor %s: clock_id=%d",
                         instance_name, clock_id)
                return clock_id
        except Exception as e:
            LOG.warning("SynceMonitor %s: clock_id parse failed: %s",
                        instance_name, e)
        return None

    def _parse_monitoring_config(self, instance_name):
        """Parse QL values from instance-monitoring.conf [<instance>] section.

        Returns dict with keys: static_ql, holdover_ql, freerun_ql.
        Values are integers (hex or decimal). Missing keys are omitted.
        """
        result = {}
        try:
            config = configparser.ConfigParser(delimiters=' ')
            config.read(constants.INSTANCE_CONFIG_PATH)
            if not config.has_section(instance_name):
                return result
            for key in ('static_ql', 'holdover_ql', 'freerun_ql'):
                if config.has_option(instance_name, key):
                    result[key] = int(config[instance_name][key], 0)
        except Exception as e:
            LOG.warning("SynceMonitor %s: monitoring config parse failed: %s",
                        instance_name, e)
        return result

    def _get_dpll(self):
        """Lazy-init and reconnect on failure."""
        if self._dpll is None:
            try:
                # Non-singleton avoids stale-socket read errors over time
                self._dpll = NetlinkDPLL(True)
            except Exception as e:
                LOG.warning("SynceMonitor: failed to init NetlinkDPLL: %s", e)
        return self._dpll

    def _read_eec_status(self):
        """Read EEC DPLL lock status filtered by clock_id."""
        dpll = self._get_dpll()
        if not dpll:
            return None
        if self._clock_id is None:
            LOG.warning("SynceMonitor %s: no clock_id configured, "
                        "cannot identify EEC device",
                        self.synce4l_service_name)
            return None
        try:
            devices = dpll.get_all_devices()
            for d in devices:
                if (d.dev_type == DeviceType.EEC
                        and d.dev_clock_id == self._clock_id):
                    return d.lock_status
            return None
        except Exception as e:
            LOG.warning("SynceMonitor: DPLL read failed: %s", e)
            self._dpll = None
            return None

    def get_synce_status(self):
        """Poll DPLL and return (new_event, sync_state, event_time).

        State machine:
          LOCKED/LOCKED_AND_HOLDOVER -> Locked
          HOLDOVER (within holdover_time) -> Holdover
          HOLDOVER (expired) or UNLOCKED -> Freerun
        """
        previous_state = self._sync_state
        current_time = datetime.datetime.now(datetime.timezone.utc).timestamp()

        raw_status = self._read_eec_status()

        if raw_status is None:
            new_state = previous_state  # no change on read failure
        elif raw_status in (LockStatus.LOCKED, LockStatus.LOCKED_AND_HOLDOVER):
            new_state = SynceState.Locked
            self._holdover_start = None
        elif raw_status == LockStatus.HOLDOVER:
            if previous_state == SynceState.Locked:
                # Just entered holdover
                self._holdover_start = current_time
                new_state = SynceState.Holdover
            elif previous_state == SynceState.Holdover:
                elapsed = current_time - (self._holdover_start or current_time)
                if elapsed < self.holdover_time:
                    new_state = SynceState.Holdover
                else:
                    new_state = SynceState.Freerun
                    LOG.warning("SyncE holdover expired (%ds >= %ds)",
                                int(elapsed), self.holdover_time)
            else:
                new_state = SynceState.Freerun
        else:
            # UNLOCKED, UNDEFINED
            new_state = SynceState.Freerun
            self._holdover_start = None

        if new_state != previous_state:
            new_event = True
            self._event_time = current_time
            LOG.info("SyncE state change: %s -> %s", previous_state, new_state)
        else:
            new_event = False

        self._sync_state = new_state
        return new_event, new_state, self._event_time

    def get_clock_quality(self):
        """Return (new_event, ql_value, event_time) for clock-quality notification.

        QL mapping (configurable via instance-monitoring.conf):
          Locked  -> locked_ql  (default 0x02 / QL-PRC)
          Holdover -> holdover_ql (default 0x04 / QL-SEC)
          Freerun  -> freerun_ql  (default 0x0f / QL-DNU)
        """
        state = self._sync_state
        if state == SynceState.Locked:
            ql = self._locked_ql
        elif state == SynceState.Holdover:
            ql = self._holdover_ql
        elif state == SynceState.Freerun:
            ql = self._freerun_ql
        else:
            ql = 0xff  # Unknown

        if ql != self._last_ql:
            self._last_ql = ql
            self._ql_event_time = datetime.datetime.now(
                datetime.timezone.utc).timestamp()
            return True, ql, self._ql_event_time
        return False, ql, self._ql_event_time
