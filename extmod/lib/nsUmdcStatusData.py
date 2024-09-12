import struct
import nsClassWriter
import time
try:
    import timetools
except:
    from ..nsUtilidades import nsuTime as timetools

import gc
import logging
from nsDataClass import NsDataClass

from constants import *

class UmdcStatusData(NsDataClass):

    _logger = logging.getLogger("UmdcStatusData")
    _logger.setLevel(logging.WARNING)


    ALARM_BIT_AC220 = 0x0001              # Alarm if there is no 220 Vac power supply
    ALARM_BIT_BATT  = 0x0002              # Alarm if battery voltage is low
    ALARM_BIT_MCB   = 0x0004              # Alarm if main circuit breaker is open

    ALARM_BIT_MB    = 0x0008              # Alarm if there are errors reading modbus

    ALARM_BIT_WIFI  = 0x4000              # Alarm if cannot connect to wifi after several trials
    ALARM_BIT_GPRS  = 0x8000              # Alarm if cannot connect GPRS after several trials



    fields = (KEY_TS, KEY_DIO, KEY_VBATT, KEY_ALARM)
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    packstring = '23sBfi'
    packlength = struct.calcsize(packstring) # 30 #bytes

    @property
    def dio(self):
        r = (0x01 if self.mcb else 0x00) 
        return r

    @dio.setter
    def dio(self, v):
        self.mcb = (v & 0x01) == 0x01
        

    @property
    def ts(self):
        return self._ts

    @ts.setter
    def ts(self, v):
        self._ts = timetools.tostr(v)

    @property
    def alarm_ac220(self):
        return (self.alarm & UmdcStatusData.ALARM_BIT_AC220) == UmdcStatusData.ALARM_BIT_AC220

    @alarm_ac220.setter
    def alarm_ac220(self, v):
        r = self.update_alarm(UmdcStatusData.ALARM_BIT_AC220, v)
        if r and v:
            self._logger.warning("220 VAC not avaliable")


    @property
    def alarm_batt(self):
        return (self.alarm & UmdcStatusData.ALARM_BIT_BATT) == UmdcStatusData.ALARM_BIT_BATT


    @alarm_batt.setter
    def alarm_batt(self, v):
        r = self.update_alarm(UmdcStatusData.ALARM_BIT_BATT, v)
        if r and v:
            self._logger.warning("BATT DEAD")

    @property
    def alarm_mcb(self):
        return (self.alarm & UmdcStatusData.ALARM_BIT_MCB) == UmdcStatusData.ALARM_BIT_MCB


    @alarm_mcb.setter
    def alarm_mcb(self, v):
        r = self.update_alarm(UmdcStatusData.ALARM_BIT_MCB, v)
        if r and v:
            self._logger.warning("Main Circuit Breaker open")

    @property
    def alarm_wifi(self):
        return (self.alarm & UmdcStatusData.ALARM_BIT_WIFI) == UmdcStatusData.ALARM_BIT_WIFI

    @alarm_wifi.setter
    def alarm_wifi(self, v):
        r=self.update_alarm(UmdcStatusData.ALARM_BIT_WIFI, v)
        if r and v:
            self._logger.warning("CANNOT CONNECT TO WIFI")

    @property
    def alarm_gprs(self):
        return (self.alarm & UmdcStatusData.ALARM_BIT_GPRS) == UmdcStatusData.ALARM_BIT_GPRS

    @alarm_gprs.setter
    def alarm_gprs(self, v):
        r = self.update_alarm(UmdcStatusData.ALARM_BIT_GPRS, v)
        if r and v:
            self._logger.warning("CANNOT CONNECT TO INTERNET USING PPP THROUGH GPRS")


    def __init__(self, ts='', vbatt=0, alarm=0):
        super(UmdcStatusData, self).__init__(alarm)
        #self.ts = timetools.totimestamp(ts)
        self._ts = timetools.tostr(ts)
        self.vbatt = vbatt
        self.alarm = alarm


    def __repr__(self):
        return "UmdcStatusData('{ts}',{vbatt},{alarm})".format(
            ts=self.ts, 
            vbatt=self.vbatt, alarm=self.alarm)

    def to_dict(self):
        d = {
            UmdcStatusData.KEY_TS : self.ts,
            UmdcStatusData.KEY_VBATT : self.vbatt,
            UmdcStatusData.KEY_ALARM : self.alarm
        }
        return d

    def to_bin(self):

        for f in self.fields:
            v = getattr(self,f)
            if v is None:
                self._logger.debug("nsUmdcStatusData - Set field {f} to 0 because it is None".format(f=f))
                setattr(self, f, 0)

        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p


    def from_dict(self, d):
        if UmdcStatusData.KEY_TS in d:
            self.ts = d[UmdcStatusData.KEY_TS]
        if UmdcStatusData.KEY_VBATT in d:
            self.vbatt = d[UmdcStatusData.KEY_VBATT]
        if UmdcStatusData.KEY_ALARM in d:
            self.alarm = d[UmdcStatusData.KEY_ALARM]

    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)

    @staticmethod
    def test():
        import machine

        rtc = machine.RTC()
        dt = rtc.datetime()
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        obj = UmdcStatusData(ts_str, 3.2, 0)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("UmdcStatusData Original -> {o}".format(o=repr(obj)))
        print ("UmdcStatusData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = UmdcStatusData()
        sw.read(p, obj2)
        print ("UmdcStatusData Unpacked -> {u}".format(u=repr(obj2)))





