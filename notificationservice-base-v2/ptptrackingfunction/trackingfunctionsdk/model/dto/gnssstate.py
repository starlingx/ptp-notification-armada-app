from wsme import types as wtypes

EnumGnssState = wtypes.Enum(str, 'Locked', 'Freerun', 'Holdover')

class GnssState(object):
    # Not all states are implemented on some hardware
    Synchronized = "SYNCHRONIZED"
    Acquiring_Sync = "ACQUIRING-SYNC"
    Antenna_Disconnected = "ANTENNA-DISCONNECTED"
    Booting = "BOOTING"
    Antenna_Short_Circuit = "ANTENNA-SHORT-CIRCUIT"
    Failure_Multipath = "FAULURE-MULTIPATH"
    Failure_Nofix = "FAILURE-NOFIX"
    Failure_Low_SNR = "FAILURE-LOW-SNR"
    Failure_PLL = "FAILURE-PLL"

