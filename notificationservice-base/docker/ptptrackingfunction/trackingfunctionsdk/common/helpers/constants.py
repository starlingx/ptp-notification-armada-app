#
# Copyright (c) 2021 Wind River Systems, Inc.
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
