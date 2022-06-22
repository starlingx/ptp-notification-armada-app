#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from wsme import types as wtypes

EnumResourceType = wtypes.Enum(str, 'PTP', 'FPGA')

class ResourceType(object):
    TypePTP = "PTP"
    TypeFPGA = "FPGA"
