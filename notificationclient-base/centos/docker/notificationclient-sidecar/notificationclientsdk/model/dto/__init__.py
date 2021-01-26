from notificationclientsdk.model.dto.subscription import SubscriptionInfo
from notificationclientsdk.model.dto.subscription import ResourceQualifierPtp

from wsme.rest.json import tojson

@tojson.when_object(SubscriptionInfo)
def subscriptioninfo_tojson(datatype, value):
    if value is None:
        return None
    return value.to_dict()

@tojson.when_object(ResourceQualifierPtp)
def resourcequalifierptp_tojson(datatype, value):
    if value is None:
        return None
    return value.to_dict()
