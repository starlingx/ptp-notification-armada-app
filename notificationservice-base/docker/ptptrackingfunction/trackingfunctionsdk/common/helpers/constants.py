#
# Copyright (c) 2021-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
from os import path

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
MASTER_MODE = "master"
TIME_IS_TRACEABLE1 = "1"
TIME_IS_TRACEABLE2 = "true"
GM_IS_PRESENT = "true"
CLOCK_CLASS_VALUE6 = "6"
CLOCK_CLASS_VALUE7 = "7"
CLOCK_CLASS_VALUE135 = "135"
CLOCK_CLASS_LOCKED_LIST = [CLOCK_CLASS_VALUE6, CLOCK_CLASS_VALUE7, CLOCK_CLASS_VALUE135]

if path.exists('/ptp/linuxptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/linuxptp/ptpinstance/'
elif path.exists('/ptp/ptpinstance'):
    LINUXPTP_CONFIG_PATH = '/ptp/ptpinstance/'
else:
    LINUXPTP_CONFIG_PATH = '/ptp/'
