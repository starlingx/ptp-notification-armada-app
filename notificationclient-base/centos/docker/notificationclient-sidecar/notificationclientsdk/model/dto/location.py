#coding=utf-8

import json

from wsme import types as wtypes
from notificationclientsdk.model.dto.resourcetype import EnumResourceType

class LocationInfo(wtypes.Base):
    NodeName = wtypes.text
    PodIP = wtypes.text
    Timestamp = float
    ResourceTypes = [EnumResourceType]

    def to_dict(self):
        d = {
                'NodeName': self.NodeName,
                'PodIP': self.PodIP,
                'Timestamp': self.Timestamp,
                'ResourceTypes': [x for x in self.ResourceTypes]
            }
        return d

    def to_orm(self):
        d = {
                'NodeName': self.NodeName,
                'PodIP': self.PodIP or '',
                'Timestamp': self.Timestamp,
                'ResourceTypes': json.dumps([x for x in self.ResourceTypes]) if self.ResourceTypes else ''
            }
        return d
