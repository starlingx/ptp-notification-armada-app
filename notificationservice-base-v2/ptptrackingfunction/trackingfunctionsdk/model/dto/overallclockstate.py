#
# Copyright (c) 2022-2023 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from wsme import types as wtypes

EnumOverallClockState = wtypes.Enum(str, 'Locked', 'Freerun', 'Holdover')


class OverallClockState(object):
    Locked = "Locked"
    Freerun = "Freerun"
    Holdover = "Holdover"
