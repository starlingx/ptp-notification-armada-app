#coding=utf-8
#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from wsme import types as wtypes
from locationservicesdk.model.dto.resourcetype import EnumResourceType

class LocationInfo(wtypes.Base):
    NodeName = wtypes.text
    PodIP = wtypes.text
    Timestamp = float
    ResourceTypes = [EnumResourceType]
