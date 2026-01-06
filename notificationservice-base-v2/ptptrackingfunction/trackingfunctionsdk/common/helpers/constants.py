#
# Copyright (c) 2021-2025 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from os import path
from pynetlink import LockStatus
import os

# phc states constants
FREERUN_PHC_STATE = "Freerun"
LOCKED_PHC_STATE = "Locked"
HOLDOVER_PHC_STATE = "Holdover"
UNKNOWN_PHC_STATE = "Unknown"
# PMC command constants
PORT_STATE = "portState"
PORT = "port{}"
GM_PRESENT = "gmPresent"
MASTER_OFFSET = "master_offset"
GM_CLOCK_CLASS = "gm.ClockClass"
TIME_TRACEABLE = "timeTraceable"
CLOCK_IDENTITY = "clockIdentity"
GRANDMASTER_IDENTITY = "grandmasterIdentity"
CLOCK_CLASS = "clockClass"
# expected values for valid ptp state
SLAVE_MODE = "slave"
MASTER_MODE = "master"
TIME_IS_TRACEABLE1 = "1"
TIME_IS_TRACEABLE2 = "true"
GM_IS_PRESENT = "true"
CLOCK_CLASS_VALUE6 = "6"
CLOCK_CLASS_VALUE7 = "7"
CLOCK_CLASS_VALUE135 = "135"
CLOCK_CLASS_LOCKED_LIST = [CLOCK_CLASS_VALUE6, CLOCK_CLASS_VALUE7, CLOCK_CLASS_VALUE135]
# ts2phc constants
NMEA_SERIALPORT = "ts2phc.nmea_serialport"
GNSS_PIN = "GNSS-1PPS"
GNSS_LOCKED_HO_ACQ = LockStatus.LOCKED_AND_HOLDOVER.value
GNSS_DPLL_0 = "DPLL0"
GNSS_DPLL_1 = "DPLL1"

UTC_OFFSET = "37"

# Notification formatting
NOTIFICATION_FORMAT = os.environ.get("NOTIFICATION_FORMAT", 'standard')

if path.exists('/ptp/linuxptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/linuxptp/ptpinstance/'
elif path.exists('/ptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/ptpinstance/'
else:
    LINUXPTP_CONFIG_PATH = '/ptp/'
PTP_CONFIG_PATH = LINUXPTP_CONFIG_PATH
PHC2SYS_CONFIG_PATH = LINUXPTP_CONFIG_PATH
TS2PHC_CONFIG_PATH = LINUXPTP_CONFIG_PATH
PHC_CTL_PATH = "/usr/sbin/phc_ctl"
PHC2SYS_DEFAULT_CONFIG = PHC2SYS_CONFIG_PATH + "phc2sys-phc2sys-legacy.conf"

CLOCK_REALTIME = "CLOCK_REALTIME"

PHC2SYS_TOLERANCE_LOW = 36999999000
PHC2SYS_TOLERANCE_HIGH = 37000001000
PHC2SYS_TOLERANCE_THRESHOLD = 1000

PTP_V1_KEY = "ptp_notification_v1"

SPEC_VERSION = "1.0"
DATA_VERSION = "1.0"
DATA_TYPE_NOTIFICATION = "notification"
DATA_TYPE_METRIC = "metric"
VALUE_TYPE_ENUMERATION = "enumeration"
VALUE_TYPE_METRIC = "metric"

SOURCE_SYNC_ALL = '/sync'
SOURCE_SYNC_GNSS_SYNC_STATUS = '/sync/gnss-status/gnss-sync-status'
SOURCE_SYNC_PTP_CLOCK_CLASS = '/sync/ptp-status/clock-class'
SOURCE_SYNC_PTP_LOCK_STATE = '/sync/ptp-status/lock-state'
SOURCE_SYNC_OS_CLOCK = '/sync/sync-status/os-clock-sync-state'
SOURCE_SYNC_SYNC_STATE = '/sync/sync-status/sync-state'
SOURCE_SYNCE_CLOCK_QUALITY = '/sync/synce-status/clock-quality'
SOURCE_SYNCE_LOCK_STATE_EXTENDED = '/sync/synce-status/lock-state-extended'
SOURCE_SYNCE_LOCK_STATE = '/sync/synce-status/lock-state'

SYS_DEV_NET = "/hostsys/bus/pci/devices/{}/net/"
SYS_DEV_NET_ADDR = "/hostsys/bus/pci/devices/{}/net/{}/phys_switch_id"
UEVENT_FILE = "/hostsys/class/gnss/{}/device/uevent"
PCI_SLOT_NAME = "PCI_SLOT_NAME"
ZL_MODULE_PATH_CLKID = "/hostsys/module/zl3073x/parameters/clock_id"
GNSS_TYPE = 'gnss'

PHC_PATH = "/hostsys/class/net/{}/device/ptp/*"

class ClockSourceType(object):
    TypePTP = "PTP"
    TypeGNSS = "GNSS"
    TypeNA = "NA"
