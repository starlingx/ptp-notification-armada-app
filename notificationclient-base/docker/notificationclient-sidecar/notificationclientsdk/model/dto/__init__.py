#
# Copyright (c) 2021-2022 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2
from notificationclientsdk.model.dto.subscription import ResourceQualifierPtp

from wsme.rest.json import tojson

@tojson.when_object(SubscriptionInfoV1)
def subscriptioninfo_tojson(datatype, value):
    if value is None:
        return None
    return value.to_dict()

@tojson.when_object(ResourceQualifierPtp)
def resourcequalifierptp_tojson(datatype, value):
    if value is None:
        return None
    return value.to_dict()

@tojson.when_object(SubscriptionInfoV2)
def subscriptioninfo_tojson(datatype, value):
    if value is None:
        return None
    return value.to_dict()
