import struct
import nsClassWriter as nsClassWriter
import time

try:
    import timetools as timetools
except:
    from ..nsUtilidades import nsuTime as timetools

    
import gc
from nsDataClass import NsDataClass

import logging
_logger = logging.getLogger("RainData")

RAINFACTOR = 1.0 # mmph per pulse

class RainData(NsDataClass):

    # Rain sensor is counting pulses continuously.
    # These pulses are read by the ULP FSM in the background while the main CPU is sleeping
    # When the main CPU wakes up, it reads the pulse count, resets the count and produces a new measure
    # Measures are spaced by at least one hour, so we do not fill the flash with data

    KEY_ID = "rainid"                   # Rain measurement Id -> int sequence
    KEY_START = "start"                 # Rain measurement period start = Previous rain measurement period end
    KEY_END = "end"                     # Rain measurement period end = Time of the new measure of pulses
    KEY_DURATION_H = "duration_h"       # Duration of the period in hours (float)
    KEY_PULSES = "pulses"               # Rain pulses read in the period (as measured by ULP FSM)
    KEY_MMPH = "mmph"                   # Pulses converted to milimeters per hour -> litres per hour
    KEY_SOIL_MOISTURE_VWC = "soil_moisture_vwc"  # Soil moisture at the time of the measure

    fields = (KEY_ID, 'ts_start','ts_end',KEY_DURATION_H, 'pulses',KEY_MMPH,KEY_SOIL_MOISTURE_VWC)
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    packstring = 'i23s23sfiff'
    packlength = struct.calcsize(packstring) # bytes 4*4 + 23*2 + 2 extra to align after text

    @property
    def ts_start(self):
        return self._ts_start
    
    @ts_start.setter
    def ts_start(self, value):
        self._ts_start = timetools.tostr(value)

    @property
    def ts_end(self):
        return self._ts_end
    
    @ts_end.setter
    def ts_end(self, value):
        self._ts_end = timetools.tostr(value)

    def __init__(self, rainid=0, ts_start='', ts_end='', pulses=0, mmph=0, soil_moisture_vwc=0):
        super(RainData, self).__init__(alarm=0)
        #self.ts_start = timetools.totimestamp(ts_start)
        #self.ts_end = timetools.totimestamp(ts_end)
        self.rainid = rainid
        self._ts_start = timetools.tostr(ts_start)
        self._ts_end = timetools.tostr(ts_end)
        self.duration_h = timetools.diff_ts_h(self.ts_end, self.ts_start)
        self.pulses = pulses
        self.mmph = mmph
        self.soil_moisture_vwc = soil_moisture_vwc



    def __repr__(self):
        return "RainData('{rainid}', '{ts_start}','{ts_end}',{duration_h},{pulses},{mmph},{soil_moisture_vwc})".format(
            rainid=self.rainid, ts_start=self.ts_start, ts_end=self.ts_end, duration_h=self.duration_h,
            pulses=self.pulses, mmph=self.mmph,
            soil_moisture_vwc=self.soil_moisture_vwc)


    def to_dict(self):
        d = {
            RainData.KEY_ID: self.rainid,
            RainData.KEY_START: self.ts_start,
            RainData.KEY_END: self.ts_end,
            RainData.KEY_DURATION_H: self.duration_h,
            RainData.KEY_PULSES: self.pulses,
            RainData.KEY_MMPH: self.mmph,
            RainData.KEY_SOIL_MOISTURE_VWC: self.soil_moisture_vwc
        }
        return d

    def to_bin(self):
        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p


    def from_dict(self, d):
        self.rainid = d[RainData.KEY_ID]
        self.ts_start = d[RainData.KEY_START]
        self.ts_end = d[RainData.KEY_END]
        if RainData.KEY_DURATION_H in d:
            self.duration_h = d[RainData.KEY_DURATION_H]
        else:
            try:
                self.duration_h = timetools.diff_ts_h(self.ts_end, self.ts_start)
            except:
                self.duration_h = 0    
        self.pulses = d[RainData.KEY_PULSES]
        self.mmph = d[RainData.KEY_MMPH]
        self.soil_moisture_vwc = d[RainData.KEY_SOIL_MOISTURE_VWC]

    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)

    @staticmethod
    def test1():
        import machine
        
        rtc = machine.RTC()
        dt = rtc.datetime()

        ts_end = time.localtime()
        ts_start = ts_end-3600

        ts_start_str = timetools.tostr(ts_start)
        ts_end_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        pulses = 30
        obj = RainData(3, ts_start_str, ts_end_str, pulses=pulses, mmph=float(pulses)/RAINFACTOR, soil_moisture_vwc=27.1)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("RainData Original -> {o}".format(o=repr(obj)))
        print ("RainData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = RainData()
        sw.read(p, obj2)
        print ("RainData Unpacked -> {u}".format(u=repr(obj2)))


    @staticmethod
    def print_rain_measures():
        import planter_pinout as PINOUT
        last_rain = RainData.getlast_in_file(PINOUT.RAIN_DATA_FN)
        li = RainData.load_from_file(PINOUT.RAIN_DATA_FN)

        if li is not None:
            for i in li:
                print(i)


    @staticmethod
    # Load rain cycles that have not been registered as communicated
    def load_not_communicated(fn_rain_data, fn_rain_communication_register):
        last_rain_measure = RainData.getlast_in_file(fn_rain_data)
        last_communicated_rain = RainDataCommunication.getlast_in_file(fn_rain_communication_register)
        if last_communicated_rain is not None:
            next_rainid = last_communicated_rain.rainid+1
        else:
            next_rainid = 0
        li_not_communicated = RainData.getsince_in_file(fn_rain_data, next_rainid)
        return (last_rain_measure, last_communicated_rain, li_not_communicated)

class RainDataCommunication(NsDataClass):

    KEY_ID = "rainid" # Rain Id -> int sequence
    
    fields = (KEY_ID,)
    packstring = 'i'
    packlength = struct.calcsize(packstring) #bytes 4

    def __init__(self, rainid=0):
        super(RainDataCommunication, self).__init__(alarm=0)
        self.rainid = rainid


    def __repr__(self):
        return "RainDataCommunication('{rainid}')".format(
            rainid=self.rainid)

    def to_dict(self):
        d = {
            RainData.KEY_ID: self.rainid,
        }
        return d

    def from_dict(self, d):
        self.rainid = d[RainData.KEY_ID]


    @staticmethod
    def test1():
        import machine
        
        obj = RainDataCommunication(3)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("RainDataCommunication Original -> {o}".format(o=repr(obj)))
        print ("RainDataCommunication Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = RainDataCommunication()
        sw.read(p, obj2)
        print ("RainDataCommunication Unpacked -> {u}".format(u=repr(obj2)))

    @staticmethod
    def print_communicated_rain_measures():
        import planter_pinout as PINOUT
        last_rain = RainDataCommunication.getlast_in_file(PINOUT.RAIN_COMMUNICATION_REGISTER_FN)
        li = RainDataCommunication.load_from_file(PINOUT.RAIN_COMMUNICATION_REGISTER_FN)

        if li is not None:
            for i in li:
                print(i)