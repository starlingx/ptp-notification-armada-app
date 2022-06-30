#
# Copyright (c) 2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#
SPEC_VERSION = "1.0"
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

VALID_SOURCE_URI = {
    SOURCE_SYNC_ALL,
    SOURCE_SYNC_GNSS_SYNC_STATUS,
    SOURCE_SYNC_PTP_CLOCK_CLASS,
    SOURCE_SYNC_PTP_LOCK_STATE,
    SOURCE_SYNC_OS_CLOCK,
    SOURCE_SYNC_SYNC_STATE,
    SOURCE_SYNCE_CLOCK_QUALITY,
    SOURCE_SYNCE_LOCK_STATE_EXTENDED,
    SOURCE_SYNCE_LOCK_STATE
}
