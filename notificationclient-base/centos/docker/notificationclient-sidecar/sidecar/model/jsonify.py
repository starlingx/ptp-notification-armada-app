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
