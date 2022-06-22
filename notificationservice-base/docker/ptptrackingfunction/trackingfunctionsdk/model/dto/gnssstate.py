from wsme import types as wtypes

EnumGnssState = wtypes.Enum(str, 'Locked', 'Freerun', 'Holdover')

class GnssState(object):
    Locked = "Locked"
    Freerun = "Freerun"
    Holdover = "Holdover"

