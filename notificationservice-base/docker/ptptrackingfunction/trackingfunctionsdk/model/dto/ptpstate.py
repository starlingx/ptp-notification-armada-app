#coding=utf-8

from wsme import types as wtypes

EnumPtpState = wtypes.Enum(str, 'Locked', 'Freerun', 'Holdover')

class PtpState(object):
    Locked = "Locked"
    Freerun = "Freerun"
    Holdover = "Holdover"

