#
# Copyright (c) 2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
import mock
import unittest
import json
import time

from dataclasses import dataclass
from trackingfunctionsdk.common.helpers import constants
from trackingfunctionsdk.model.dto.osclockstate import OsClockState
from trackingfunctionsdk.model.dto.overallclockstate import OverallClockState
from trackingfunctionsdk.model.dto.ptpstate import PtpState
from trackingfunctionsdk.model.dto.gnssstate import GnssState
from trackingfunctionsdk.services.daemon import PtpWatcherDefault

context = {
    "THIS_NAMESPACE": "notification",
    "THIS_NODE_NAME": "controller-0",
    "THIS_POD_IP": "172.16.192.71",
    "REGISTRATION_TRANSPORT_ENDPOINT": "rabbit://admin:admin@registration.notification.svc.cluster.local:5672",
    "NOTIFICATION_TRANSPORT_ENDPOINT": "rabbit://admin:admin@172.16.192.71:5672",
    "GNSS_CONFIGS": [
        "/ptp/linuxptp/ptpinstance/ts2phc-ts1.conf",
        "/ptp/linuxptp/ptpinstance/ts2phc-ts2.conf",
    ],
    "PHC2SYS_CONFIG": "/ptp/linuxptp/ptpinstance/phc2sys-phc-inst1.conf",
    "PHC2SYS_SERVICE_NAME": "phc-inst1",
    "PTP4L_CONFIGS": [
        "/ptp/linuxptp/ptpinstance/ptp4l-ptp-inst2.conf",
        "/ptp/linuxptp/ptpinstance/ptp4l-ptp-inst1.conf",
    ],
    "GNSS_INSTANCES": ["ts1", "ts2"],
    "PTP4L_INSTANCES": ["ptp-inst2", "ptp-inst1"],
    "ptptracker_context": {"device_simulated": "false", "holdover_seconds": "15"},
    "gnsstracker_context": {"holdover_seconds": 30},
    "osclocktracker_context": {"holdover_seconds": "15"},
    "overalltracker_context": {"holdover_seconds": "15"},
}


@dataclass
class OsClockData:
    sync_state: str = OsClockState.Freerun
    sync_source: str = "ptp0"


@dataclass
class PTP4lData:
    ptp_devices: list[str]
    sync_state: str = PtpState.Freerun
    sync_source: str = constants.ClockSourceType.TypePTP


@dataclass
class ts2phcData:
    ptp_devices: list[str]
    sync_state: str = GnssState.Failure_Nofix


@dataclass
class TestData:
    osclock: OsClockData
    ptp4l: list[PTP4lData]
    ts2phc: list[ts2phcData]


class DaemonTests(unittest.TestCase):

    @mock.patch("trackingfunctionsdk.services.daemon.PtpMonitor")
    @mock.patch("trackingfunctionsdk.services.daemon.OsClockMonitor")
    @mock.patch("trackingfunctionsdk.services.daemon.GnssMonitor")
    def _setup(self, gnssmonitor_mock, osclockmonitor_mock, ptpmonitor_mock):
        event = None

        sqlalchemy_conf = {
            "url": "sqlite:///apiserver.db",
            "echo": False,
            "echo_pool": False,
            "pool_recycle": 3600,
            "encoding": "utf-8",
        }
        sqlalchemy_conf_json = json.dumps(sqlalchemy_conf)
        daemon_context_json = json.dumps(context)

        # distint mock class instances, to have distinct mock method on instance basis
        gnssmonitor_mock.side_effect = [
            mock.Mock(name=item) for item in context["GNSS_CONFIGS"]
        ]
        ptpmonitor_mock.side_effect = [
            mock.Mock(name=item) for item in context["PTP4L_CONFIGS"]
        ]

        self.worker = PtpWatcherDefault(
            event, sqlalchemy_conf_json, daemon_context_json
        )

        self.osclockmonitor_mock_instance = self.worker.os_clock_monitor
        self.ptpmonitor_mock_instances = self.worker.ptp_monitor_list
        self.gnssmonitor_mock_instances = self.worker.observer_list

        self.assertEqual(
            len(self.gnssmonitor_mock_instances), len(context["GNSS_CONFIGS"])
        )
        self.assertEqual(
            len(self.ptpmonitor_mock_instances), len(context["PTP4L_CONFIGS"])
        )

    def _test__get_overall_sync_state(self, testdata, expected):
        holdover_time = float(context["overalltracker_context"]["holdover_seconds"])
        freq = 2
        sync_state = OverallClockState.Freerun
        last_event_time = time.time()

        self.osclockmonitor_mock_instance.get_source_ptp_device.return_value = (
            testdata.osclock.sync_source
        )
        self.osclockmonitor_mock_instance.get_os_clock_state.return_value = (
            testdata.osclock.sync_state
        )
        # test mocking as expected or not.
        self.assertEqual(
            self.worker.os_clock_monitor.get_source_ptp_device(),
            testdata.osclock.sync_source,
        )
        self.assertEqual(
            self.worker.os_clock_monitor.get_os_clock_state(),
            testdata.osclock.sync_state,
        )

        for i, gnssmonitor_mock_instance in enumerate(self.gnssmonitor_mock_instances):
            gnssmonitor_mock_instance.get_ptp_devices.return_value = testdata.ts2phc[
                i
            ].ptp_devices
            gnssmonitor_mock_instance._state = testdata.ts2phc[i].sync_state
        # test mocking as expected or not.
        self.assertEqual(
            self.gnssmonitor_mock_instances[0].get_ptp_devices(),
            testdata.ts2phc[0].ptp_devices,
        )
        self.assertEqual(
            self.gnssmonitor_mock_instances[0]._state, testdata.ts2phc[0].sync_state
        )
        self.assertEqual(
            self.gnssmonitor_mock_instances[1].get_ptp_devices(),
            testdata.ts2phc[1].ptp_devices,
        )
        self.assertEqual(
            self.gnssmonitor_mock_instances[1]._state, testdata.ts2phc[1].sync_state
        )

        for i, ptpmonitor_mock_instance in enumerate(self.ptpmonitor_mock_instances):
            ptpmonitor_mock_instance.get_ptp_devices.return_value = testdata.ptp4l[
                i
            ].ptp_devices
            ptpmonitor_mock_instance.get_ptp_sync_state.return_value = (
                None,
                testdata.ptp4l[i].sync_state,
                None,
            )
            ptpmonitor_mock_instance.get_ptp_sync_source.return_value = testdata.ptp4l[
                i
            ].sync_source
        # test mocking as expected or not.
        self.assertEqual(
            self.ptpmonitor_mock_instances[0].get_ptp_devices(),
            testdata.ptp4l[0].ptp_devices,
        )
        self.assertEqual(
            self.ptpmonitor_mock_instances[0].get_ptp_sync_state(),
            (None, testdata.ptp4l[0].sync_state, None),
        )
        self.assertEqual(
            self.ptpmonitor_mock_instances[0].get_ptp_sync_source(),
            testdata.ptp4l[0].sync_source,
        )
        self.assertEqual(
            self.ptpmonitor_mock_instances[1].get_ptp_devices(),
            testdata.ptp4l[1].ptp_devices,
        )
        self.assertEqual(
            self.ptpmonitor_mock_instances[1].get_ptp_sync_state(),
            (None, testdata.ptp4l[1].sync_state, None),
        )
        self.assertEqual(
            self.ptpmonitor_mock_instances[1].get_ptp_sync_source(),
            testdata.ptp4l[1].sync_source,
        )

        new_event, sync_state, new_event_time = (
            self.worker._PtpWatcherDefault__get_overall_sync_state(
                holdover_time, freq, sync_state, last_event_time
            )
        )
        # overall sync state assertion
        self.assertEqual(sync_state, expected)

    def test__get_overall_sync_state__all_are_locked__overall_locked(self):
        # when all are locked state -- overall state would be locked
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Locked
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__osclock_freerun__overall_freerun(self):
        # when osclock is on freerun, and others are on locked state -- overall
        # state would be freerun
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Freerun, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__ptp4l_ptp0_freerun__overall_freerun(self):
        # when chained ptp4l ptp0 sync_state is freerun -- overall state would be freerun
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Freerun,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__ptp4l_ptp0_locked__overall_locked(self):
        # when chained ptp4l ptp0 sync_state is locked -- overall state would be locked
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Freerun,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Failure_Nofix
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Failure_Nofix
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Locked
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__ts2phc_ptp0_freerun__overall_freerun(self):
        # when chained ts2phc ptp0 sync_state is freerun -- overall state would be freerun
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypeGNSS,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Failure_Nofix
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__ts2phc_ptp0_locked__overall_locked(self):
        # when chained ts2phc ptp0 sync_state is locked -- overall state would be locked
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypeGNSS,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Freerun,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Failure_Nofix
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Locked
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__ts2phc_ptp0_locked_no_ptp4l_for_ptp0__overall_locked(
        self,
    ):
        # when chained ts2phc ptp0 sync_state is locked -- overall state would be locked
        # In this case there are no ptp4l instances with ptp0
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptpx"],
            sync_state=PtpState.Freerun,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Freerun,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Failure_Nofix
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Locked
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__no_source_for_ptp0__overall_freerun(self):
        # when chained ptp4l ptp0 sync_source NA (neither gnss nor ptp) -- overall
        # state would be freerun
        # In this case there are no ts2phc instances with ptp0
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        # In this case, practically ptp0's ptp4l instance sync_state would be
        # PtpState.Freerun, as there is no sync source. But still using locked state.
        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypeNA,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptpx"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__no_backtrack_for_ptp0__overall_freerun(self):
        # when chained ptp0 is not included neither on ptp4l nor ts2phc -- overall
        # state would be freerun
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source="ptp0")

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptpx"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptpx"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)

    def test__get_overall_sync_state__os_clock_no_ptp_device__overall_freerun(self):
        # when there is no sync_source e.g. ptp0 for os_clock -- overall state would be freerun
        self._setup()
        osclockdata = OsClockData(sync_state=OsClockState.Locked, sync_source=None)

        ptp4ldata0 = PTP4lData(
            ptp_devices=["ptp0"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )
        ptp4ldata1 = PTP4lData(
            ptp_devices=["ptp1"],
            sync_state=PtpState.Locked,
            sync_source=constants.ClockSourceType.TypePTP,
        )

        ts2phcdata0 = ts2phcData(
            ptp_devices=["ptp0"], sync_state=GnssState.Synchronized
        )
        ts2phcdata1 = ts2phcData(
            ptp_devices=["ptp1"], sync_state=GnssState.Synchronized
        )

        testdata = TestData(
            osclock=osclockdata,
            ptp4l=[ptp4ldata0, ptp4ldata1],
            ts2phc=[ts2phcdata0, ts2phcdata1],
        )
        expected = OverallClockState.Freerun
        self._test__get_overall_sync_state(testdata, expected)
