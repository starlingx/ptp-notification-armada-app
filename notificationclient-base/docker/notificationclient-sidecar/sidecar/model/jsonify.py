#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from notificationclientsdk.model.dto.subscription import SubscriptionInfoV1
from notificationclientsdk.model.dto.subscription import SubscriptionInfoV2
from notificationclientsdk.model.dto.subscription import ResourceQualifierPtp

from pecan.jsonify import jsonify

@jsonify.register(SubscriptionInfoV1)
def jsonify_subscriptioninfo(subscriptionInfo):
    return subscriptionInfo.to_dict()

@jsonify.register(ResourceQualifierPtp)
def jsonify_resourcequalifierptp(resourceQualifierPtp):
    return resourceQualifierPtp.to_dict()

@jsonify.register(SubscriptionInfoV2)
def jsonify_subscriptioninfo(subscriptionInfo):
    return subscriptionInfo.to_dict()

def __init__():
  pass
