import struct
import nsClassWriter
import time
try:
    import timetools
except:
    from ..nsUtilidades import nsuTime as timetools

import gc

from nsDataClass import NsDataClass

class Power3ChData(NsDataClass):


    KEY_TICKS_MS= "ticks_ms"
    KEY_V1 = "v1"
    KEY_I1 = "i1"
    KEY_V2 = "v2"
    KEY_I2 = "i2"
    KEY_V3 = "v3"
    KEY_I3 = "i3"

    fields = (KEY_TICKS_MS,KEY_V1,KEY_I1,KEY_V2,KEY_I2,KEY_V3,KEY_I3)
    packstring = 'iffffff'
    packlength = struct.calcsize(packstring) # 7x4 = 28 bytes

    def __init__(self, ticks_ms=0, v1=0, i1=0, v2=0, i2=0, v3=0, i3=0):
        super(Power3ChData, self).__init__(alarm=0)
        self.ticks_ms = ticks_ms
        self.v1 = v1
        self.i1 = i1
        self.v2 = v2
        self.i2 = i2
        self.v3 = v3
        self.i3 = i3


    def __repr__(self):
        return "Power3ChData('{ticks_ms}','{v1}',{i1},'{v2}',{i2},'{v3}',{i3})".format(
            ticks_ms=self.ticks_ms, v1=self.v1, i1=self.i1, v2=self.v2, i2=self.i2, v3=self.v3, i3=self.i3)


    def get_ch(self, n):
        if n == 1:
            return (self.v1, self.i1)
        elif n == 2:
            return (self.v2, self.i2)
        elif n == 3:
            return (self.v3, self.i3)
        else:
            return None

    def to_dict(self):
        d = {
            Power3ChData.KEY_TICKS_MS: self.ticks_ms,
            Power3ChData.KEY_V1: self.v1,
            Power3ChData.KEY_I1: self.i1,
            Power3ChData.KEY_V2: self.v2,
            Power3ChData.KEY_I2: self.i2,
            Power3ChData.KEY_V3: self.v3,
            Power3ChData.KEY_I3: self.i3,
        }
        return d

    def to_bin(self):
        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p

    def from_dict(self, d):
        self.ticks_ms = d[Power3ChData.KEY_TICKS_MS]
        self.v1 = d[Power3ChData.KEY_V1]
        self.i1 = d[Power3ChData.KEY_I1]
        self.v2 = d[Power3ChData.KEY_V2]
        self.i2 = d[Power3ChData.KEY_I2]
        self.v3 = d[Power3ChData.KEY_V3]
        self.i3 = d[Power3ChData.KEY_I3]
        
    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)


    @staticmethod
    def test1():
        import machine
        import utime
        
        rtc = machine.RTC()
        dt = rtc.datetime()
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        ticks_ms = utime.ticks_ms()

        obj = Power3ChData(ticks_ms, 12.04, 1.26, 12.43, 0.750, 18.28, 0.53)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("Power3ChData Original -> {o}".format(o=repr(obj)))
        print ("Power3ChData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = Power3ChData()
        sw.read(p, obj2)
        print ("Power3ChData Unpacked -> {u}".format(u=repr(obj2)))




class Power1ChData(NsDataClass):


    KEY_TICKS_MS= "ticks_ms"
    KEY_V1 = "v1"
    KEY_I1 = "i1"

    fields = (KEY_TICKS_MS,KEY_V1,KEY_I1)
    packstring = 'iff'
    packlength = struct.calcsize(packstring) # 12 #bytes

    def __init__(self, ticks_ms=0, v1=0, i1=0):
        super(Power1ChData, self).__init__(alarm=0)
        self.ticks_ms = ticks_ms
        self.v1 = v1
        self.i1 = i1



    def __repr__(self):
        return "Power3ChData('{ticks_ms}','{v1}',{i1})".format(
            ticks_ms=self.ticks_ms, v1=self.v1, i1=self.i1)

    def get_ch(self, n):
        if n == 1:
            return (self.v1, self.i1)
        else:
            return None

    def to_dict(self):
        d = {
            Power1ChData.KEY_TICKS_MS: self.ticks_ms,
            Power1ChData.KEY_V1: self.v1,
            Power1ChData.KEY_I1: self.i1,
        }
        return d

    def to_bin(self):
        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p

    def from_dict(self, d):
        self.ticks_ms = d[Power1ChData.KEY_TICKS_MS]
        self.v1 = d[Power1ChData.KEY_V1]
        self.i1 = d[Power1ChData.KEY_I1]

    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)


    @staticmethod
    def test1():
        import machine
        import utime
        
        rtc = machine.RTC()
        dt = rtc.datetime()
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        ticks_ms = utime.ticks_ms()

        obj = Power1ChData(ticks_ms, 12.04, 1.26)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("Power1ChData Original -> {o}".format(o=repr(obj)))
        print ("Power1ChData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = Power1ChData()
        sw.read(p, obj2)
        print ("Power1ChData Unpacked -> {u}".format(u=repr(obj2)))

