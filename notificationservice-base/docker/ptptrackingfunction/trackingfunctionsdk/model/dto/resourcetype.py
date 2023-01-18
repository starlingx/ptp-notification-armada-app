#coding=utf-8

from wsme import types as wtypes

EnumResourceType = wtypes.Enum(str, 'PTP', 'FPGA')

class ResourceType(object):
    TypePTP = "PTP"
    TypeFPGA = "FPGA"
