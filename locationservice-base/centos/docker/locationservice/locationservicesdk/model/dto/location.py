#coding=utf-8

from wsme import types as wtypes
from locationservicesdk.model.dto.resourcetype import EnumResourceType

class LocationInfo(wtypes.Base):
    NodeName = wtypes.text
    PodIP = wtypes.text
    Timestamp = float
    ResourceTypes = [EnumResourceType]
