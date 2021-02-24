#
# Copyright (c) 2021 Wind River Systems, Inc.
#
# SPDX-License-Identifier: Apache-2.0
#

from notificationclientsdk.model.dto.subscription import SubscriptionInfo
from notificationclientsdk.model.dto.subscription import ResourceQualifierPtp

from pecan.jsonify import jsonify

@jsonify.register(SubscriptionInfo)
def jsonify_subscriptioninfo(subscriptionInfo):
    return subscriptionInfo.to_dict()

@jsonify.register(ResourceQualifierPtp)
def jsonify_resourcequalifierptp(resourceQualifierPtp):
    return resourceQualifierPtp.to_dict()

def __init__():
  pass
