#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

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
TIME_IS_TRACEABLE1 = "1"
TIME_IS_TRACEABLE2 = "true"
GM_IS_PRESENT = "true"
CLOCK_CLASS_VALUE1 = "6"
CLOCK_CLASS_VALUE2 = "7"
CLOCK_CLASS_VALUE3 = "135"
# ts2phc constants
NMEA_SERIALPORT = "ts2phc.nmea_serialport"
GNSS_PIN = "GNSS-1PPS"
GNSS_LOCKED_HO_ACK = 'locked_ho_ack'
GNSS_DPLL_0 = "DPLL0"
GNSS_DPLL_1 = "DPLL1"

UTC_OFFSET = "37"
PTP_CONFIG_PATH = "/ptp/ptpinstance/"
PHC_CTL_PATH = "/usr/sbin/phc_ctl"
PHC2SYS_DEFAULT_CONFIG = "/ptp/ptpinstance/phc2sys-phc2sys-legacy.conf"
PHC2SYS_CONF_PATH = "/ptp/ptpinstance/"

CLOCK_REALTIME = "CLOCK_REALTIME"

PHC2SYS_TOLERANCE_LOW = 36999999000
PHC2SYS_TOLERANCE_HIGH = 37000001000

# testing values
CGU_PATH_VALID = "/sys/kernel/debug/ice/0000:18:00.0/cgu"

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
