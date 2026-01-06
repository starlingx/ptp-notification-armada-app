#coding=utf-8

from wsme import types as wtypes
from trackingfunctionsdk.model.dto.resourcetype import EnumResourceType
from trackingfunctionsdk.model.dto.ptpstate import PtpState

class PtpStatus(wtypes.Base):
    EventTimestamp = float
    ResourceType = EnumResourceType
    EventData_State = PtpState
    ResourceQualifier_NodeName = wtypes.text

    def to_dict(self):
        d = {
                'EventTimestamp': self.EventTimestamp,
                'ResourceType': self.ResourceType,
                'EventData': {
                    'State': self.EventData_State
                    },
                'ResourceQualifier': {
                    'NodeName': self.ResourceQualifier_NodeName
                }
            }
        return d
