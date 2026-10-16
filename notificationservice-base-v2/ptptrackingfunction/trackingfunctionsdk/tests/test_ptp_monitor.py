#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import glob
import json
import mock
import os
import time
import unittest

from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.common.helpers.ptp_monitor import PtpMonitor

testpath = os.environ.get("TESTPATH", "")

holdover_seconds = 15
poll_freq_seconds = 15
phc2sys_service_name = "phc-inst1"
ptp4l_instance = "ptp-inst1"


class PtpMonitorTests(unittest.TestCase):

    def test_check_config_file_interfaces(self):
        self.ptpmon = PtpMonitor(
            ptp4l_instance,
            holdover_seconds,
            phc2sys_service_name,
            init=False,
        )
        self.ptpmon.ptp4l_config = testpath + "test_input_files/ptp4l-ptp-inst1.conf"
        self.assertEqual(
            self.ptpmon._check_config_file_interfaces(), [
                "enp81s0f3", "enp81s0f4"])

    def test_set_ptp_devices(self):
        self.ptpmon = PtpMonitor(
            ptp4l_instance,
            holdover_seconds,
            phc2sys_service_name,
            init=False,
        )
        self.ptpmon.ptp4l_config = testpath + "test_input_files/ptp4l-ptp-inst1.conf"

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob", return_value=[]
        ):
            self.ptpmon.set_ptp_devices()
        self.assertEqual(self.ptpmon.get_ptp_devices(), [])

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob",
            side_effect=[
                ["/hostsys/class/net/enp81s0f3/device/ptp/ptp0"],
                ["/hostsys/class/net/enp81s0f4/device/ptp/ptp1"],
            ],
        ):
            self.ptpmon.set_ptp_devices()
        self.assertEqual(set(self.ptpmon.get_ptp_devices()),
                         set(["ptp0", "ptp1"]))

        with mock.patch(
            "trackingfunctionsdk.common.helpers.ptpsync.glob",
            side_effect=[
                ["/hostsys/class/net/enp81s0f3/device/ptp/ptp0"],
                ["/hostsys/class/net/enp81s0f4/device/ptp/ptp0"],
            ],
        ):
            self.ptpmon.set_ptp_devices()

        self.assertEqual(self.ptpmon.get_ptp_devices(), ["ptp0"])


class PtpMonitorFreeRunningTests(unittest.TestCase):
    """Tests for the dpll-mgr PTP-backhaul Monitoring remap.

    The dpll-mgr PTP-backhaul monitor is parked by dpll-mgr while GNSS is the
    active source and so is reported Freerun by check_results(). When it is
    healthy (GM present + locked clockClass) it must instead be reported as
    the Monitoring state. The remap is gated on the dpll-mgr backhaul identity
    (is_dpll_mgr_backhaul), not on free_running.
    """

    def _make_monitor(self, config):
        mon = PtpMonitor(
            ptp4l_instance,
            holdover_seconds,
            phc2sys_service_name,
            init=False,
        )
        mon.ptp4l_config = config
        mon.ptp4l_service_name = "ptp-bh"
        mon.phc2sys_service_name = phc2sys_service_name
        mon.offset_threshold = 0
        # init=False skips __init__ attribute setup that ptp_status() relies on
        mon.sync_source = constants.ClockSourceType.TypeNA
        mon._ptp_sync_state = constants.UNKNOWN_PHC_STATE
        mon._ptp_event_time = time.time()
        return mon

    def test_detect_dpll_mgr_backhaul_matches_ptp_bh_uds(self):
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.uds_address = "/var/run/ptp4l-ptp-bh"
        dpll_config = {
            "channels": {
                "ptp_bh": {"call_channel": "uds:/var/run/ptp4l-ptp-bh"},
                "ts2_0": {"call_channel": "uds:/var/run/ts2phc-ts1"},
            }
        }
        with mock.patch.object(
                glob, "glob",
                return_value=["/ptp/dpll-mgr-dpll-mgr1.json"]), \
                mock.patch("builtins.open",
                           mock.mock_open(read_data=json.dumps(dpll_config))):
            self.assertTrue(mon._detect_dpll_mgr_backhaul())

    def test_detect_dpll_mgr_backhaul_non_bh_instance(self):
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-inst1.conf")
        mon.uds_address = "/var/run/ptp4l-ptp01fh"
        dpll_config = {
            "channels": {
                "ptp_bh": {"call_channel": "uds:/var/run/ptp4l-ptp-bh"},
            }
        }
        with mock.patch.object(
                glob, "glob",
                return_value=["/ptp/dpll-mgr-dpll-mgr1.json"]), \
                mock.patch("builtins.open",
                           mock.mock_open(read_data=json.dumps(dpll_config))):
            self.assertFalse(mon._detect_dpll_mgr_backhaul())

    def test_detect_dpll_mgr_backhaul_no_dpll_mgr(self):
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.uds_address = "/var/run/ptp4l-ptp-bh"
        with mock.patch.object(glob, "glob", return_value=[]):
            self.assertFalse(mon._detect_dpll_mgr_backhaul())

    def _run_ptp_status(self, mon, check_results_return, pmc_results):
        from trackingfunctionsdk.common.helpers import ptpsync as utils
        with mock.patch.object(
                utils, "check_critical_resources",
                return_value=(True, True, True, True)), \
                mock.patch.object(
                    mon, "ptpsync",
                    return_value=(pmc_results, len(pmc_results), 1)), \
                mock.patch.object(
                    utils, "check_results",
                    return_value=check_results_return):
            return mon.ptp_status()

    def test_backhaul_healthy_reports_monitoring(self):
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        pmc = {
            constants.GM_PRESENT: "true",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE6,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertEqual(state, PtpState.Monitoring)

    def test_backhaul_no_gm_stays_freerun(self):
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        pmc = {
            constants.GM_PRESENT: "false",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE248,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertEqual(state, PtpState.Freerun)

    def test_backhaul_bad_clockclass_stays_freerun(self):
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        pmc = {
            constants.GM_PRESENT: "true",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE248,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertEqual(state, PtpState.Freerun)

    def test_backhaul_slave_reports_locked(self):
        # On failover dpll-mgr drives the backhaul; its port reaches SLAVE and
        # check_results() reports Locked. The Monitoring remap only applies to
        # the Freerun (parked/UNCALIBRATED) case, so Locked passes through.
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        pmc = {
            constants.GM_PRESENT: "true",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE6,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Locked, constants.ClockSourceType.TypePTP), pmc)
        self.assertEqual(state, PtpState.Locked)

    def test_non_backhaul_not_monitoring(self):
        # A normal (non dpll-mgr-backhaul) instance reported Freerun must stay
        # Freerun even with GM present -- the override is gated on the
        # dpll-mgr backhaul identity.
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-inst1.conf")
        mon.is_dpll_mgr_backhaul = False
        pmc = {
            constants.GM_PRESENT: "true",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE6,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertNotEqual(state, PtpState.Monitoring)

    def test_backhaul_gm_lost_from_monitoring_enters_holdover(self):
        # When the backhaul was Monitoring and the GM is lost, it enters
        # HOLDOVER (consistent with other ptp4l instances), not Freerun
        # directly.
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        mon.holdover_time = 60
        mon._ptp_sync_state = PtpState.Monitoring       # previous = Monitoring
        mon._ptp_event_time = time.time()
        # GM lost -> check_results reports Freerun, gmPresent false
        pmc = {
            constants.GM_PRESENT: "false",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE248,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertEqual(state, PtpState.Holdover)

    def test_backhaul_holdover_expires_to_freerun(self):
        # After holdover_time elapses, the backhaul instance in
        # HOLDOVER decays to FREERUN.
        from trackingfunctionsdk.common.helpers import constants
        from trackingfunctionsdk.model.dto.ptpstate import PtpState
        mon = self._make_monitor(
            testpath + "test_input_files/ptp4l-ptp-bh.conf")
        mon.is_dpll_mgr_backhaul = True
        mon.holdover_time = 60
        mon._ptp_sync_state = PtpState.Holdover         # previous = Holdover
        mon._ptp_event_time = time.time() - 120         # 120s ago > 60s
        pmc = {
            constants.GM_PRESENT: "false",
            constants.GM_CLOCK_CLASS: constants.CLOCK_CLASS_VALUE248,
        }
        _, state, _ = self._run_ptp_status(
            mon, (PtpState.Freerun, constants.ClockSourceType.TypeNA), pmc)
        self.assertEqual(state, PtpState.Freerun)
