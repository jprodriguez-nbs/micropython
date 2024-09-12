import struct
import nsClassWriter as nsClassWriter
import time

try:
    import timetools
except:
    from ..nsUtilidades import nsuTime as timetools

    
import gc
from nsDataClass import NsDataClass

import logging
_logger = logging.getLogger("IrrigationData")

class IrrigationData(NsDataClass):

    KEY_IRRIGATIONID = "irrigationid" # Irrigation Id -> int sequence
    KEY_START = "start"
    KEY_END = "end"
    KEY_DURATION = "duration"
    KEY_PULSES = "pulses"
    KEY_VOL_L = "vol_l"
    KEY_CE_MWH = "ce_mwh"
    KEY_VBATT = "vbatt"
    KEY_VPUMP = "vpump"
    KEY_IPUMP = "ipump"
    KEY_INITIAL_SOIL_MOISTURE_VWC = "initial_sm_vwc"
    KEY_FINAL_SOIL_MOISTURE_VWC = "final_sm_vwc"

    fields = (KEY_IRRIGATIONID, 'ts_start','ts_end',KEY_DURATION, 'pulses','vol_l','ce_mwh','vbatt','vpump','ipump', KEY_INITIAL_SOIL_MOISTURE_VWC, KEY_FINAL_SOIL_MOISTURE_VWC)
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    packstring = 'i23s23sfifffffff'
    packlength = struct.calcsize(packstring) #bytes 10*4 + 23*2 + 2 extra to align after text

    def __init__(self, irrigationid=0, ts_start='', ts_end='', duration=0.0, pulses=0, 
                vol_l=0.0, ce_mwh=0.0, vbatt=0.0, vpump=0.0, ipump=0.0, 
                initial_sm_vwc=0.0, final_sm_vwc=0.0):

        super(IrrigationData, self).__init__(alarm=0)
        #self.ts_start = timetools.totimestamp(ts_start)
        #self.ts_end = timetools.totimestamp(ts_end)
        self.irrigationid = irrigationid
        self.ts_start = timetools.tostr(ts_start)
        self.ts_end = timetools.tostr(ts_end)
        self.duration = duration
        self.pulses = pulses
        self.vol_l = vol_l
        self.ce_mwh = ce_mwh
        self.vbatt = vbatt
        self.vpump = vpump
        self.ipump = ipump
        self.initial_sm_vwc = initial_sm_vwc
        self.final_sm_vwc = final_sm_vwc



    def __repr__(self):
        return "IrrigationData('{irrigationid}', '{ts_start}','{ts_end}',{duration:.1f},{pulses},{vol_l},{ce_mwh},{vbatt},{vpump},{ipump},{initial_sm_vwc},{final_sm_vwc})".format(
            irrigationid=self.irrigationid, ts_start=self.ts_start, ts_end=self.ts_end, duration=self.duration, pulses=self.pulses, vol_l=self.vol_l,
            ce_mwh=self.ce_mwh, vbatt=self.vbatt, vpump=self.vpump, ipump=self.ipump, initial_sm_vwc=self.initial_sm_vwc, final_sm_vwc=self.final_sm_vwc)

    def end(self, ts_end, duration, pulses, vol_l, ce_mwh, vpump, ipump):
        self.ts_end = timetools.tostr(ts_end)
        self.duration = duration
        self.pulses = pulses
        self.vol_l = vol_l
        self.ce_mwh = ce_mwh
        self.vpump = vpump
        self.ipump = ipump

    def to_dict(self):
        d = {
            IrrigationData.KEY_IRRIGATIONID: self.irrigationid,
            IrrigationData.KEY_START: self.ts_start,
            IrrigationData.KEY_END: self.ts_end,
            IrrigationData.KEY_DURATION: self.duration,
            IrrigationData.KEY_PULSES: self.pulses,
            IrrigationData.KEY_VOL_L: self.vol_l,
            IrrigationData.KEY_CE_MWH: self.ce_mwh,
            IrrigationData.KEY_VBATT: self.vbatt,
            IrrigationData.KEY_VPUMP: self.vpump,
            IrrigationData.KEY_IPUMP: self.ipump,
            IrrigationData.KEY_INITIAL_SOIL_MOISTURE_VWC: self.initial_sm_vwc,
            IrrigationData.KEY_FINAL_SOIL_MOISTURE_VWC: self.final_sm_vwc
        }
        return d


    def to_bin(self):
        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p

    def from_dict(self, d):
        self.irrigationid = d[IrrigationData.KEY_IRRIGATIONID]
        self.ts_start = d[IrrigationData.KEY_START]
        self.ts_end = d[IrrigationData.KEY_END]
        if IrrigationData.KEY_DURATION in d:
            self.duration = d[IrrigationData.KEY_DURATION]
        else:
            if "duration_ms" in d:
                self.duration = float(d['duration_ms'])/1000.0
            else:
                try:
                    self.duration = (timetools.diff_ts_ms(self.ts_end, self.ts_start))/1000.0
                except:
                    self.duration = 0   

        self.pulses = d[IrrigationData.KEY_PULSES]
        self.vol_l = d[IrrigationData.KEY_VOL_L]
        self.ce_mwh = d[IrrigationData.KEY_CE_MWH]
        self.vbatt = d[IrrigationData.KEY_VBATT]
        self.vpump = d[IrrigationData.KEY_VPUMP]
        self.ipump = d[IrrigationData.KEY_IPUMP]
        if IrrigationData.KEY_INITIAL_SOIL_MOISTURE_VWC in d:
            self.initial_sm_vwc = d[IrrigationData.KEY_INITIAL_SOIL_MOISTURE_VWC]
        else:
            self.initial_sm_vwc = 0

        if IrrigationData.KEY_FINAL_SOIL_MOISTURE_VWC in d:
            self.final_sm_vwc = d[IrrigationData.KEY_FINAL_SOIL_MOISTURE_VWC]
        else:
            if 'soil_moisture_vwc' in d:
                self.final_sm_vwc = d['soil_moisture_vwc']

    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)


    @staticmethod
    def test1():
        import machine
        
        rtc = machine.RTC()
        dt = rtc.datetime()
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        obj = IrrigationData(3, ts_str, ts_str, 50234, 2496, 4.37, 1239.9, 11.9, 11.4, 1245.4, 22.3, 32.1)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("IrrigationData Original -> {o}".format(o=repr(obj)))
        print ("IrrigationData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = IrrigationData()
        sw.read(p, obj2)
        print ("IrrigationData Unpacked -> {u}".format(u=repr(obj2)))


    @staticmethod
    def test2():
        import machine
        
        rtc = machine.RTC()
        dt = rtc.datetime()
        obj = IrrigationData(4, dt, dt, 40236, 2496, 4.37, 1239.9, 11.9, 11.4, 1245.4, 22.82, 33.41)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("IrrigationData Original -> {o}".format(o=repr(obj)))
        print ("IrrigationData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = IrrigationData()
        sw.read(p, obj2)
        print ("IrrigationData Unpacked -> {u}".format(u=repr(obj2)))

    @staticmethod
    def test3():
        import machine
        
        rtc = machine.RTC()
        dt = rtc.datetime()
        ts = time.mktime(dt)
        obj = IrrigationData(9, ts, ts, 51224, 2496, 4.37, 1239.9, 11.9, 11.4, 1245.4, 22.32, 33.43)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("IrrigationData Original -> {o}".format(o=repr(obj)))
        print ("IrrigationData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = IrrigationData()
        sw.read(p, obj2)
        print ("IrrigationData Unpacked -> {u}".format(u=repr(obj2)))


    @staticmethod
    def print_irrigation_cycles(fn):
        #import planter_pinout as PINOUT
        #fn=PINOUT.IRRIGATION_DATA_FN
        last_irrigation = IrrigationData.getlast_in_file(fn)
        li = IrrigationData.load_from_file(fn)

        if li is not None:
            for i in li:
                print(i)

    @staticmethod
    # Load irrigation cycles that have not been registered as communicated
    def load_not_communicated(fn_irrigation_data, fn_irrigation_communication_register):
        last_irrigation_cycle = IrrigationData.getlast_in_file(fn_irrigation_data)
        last_communicated_irrigation = IrrigationDataCommunication.getlast_in_file(fn_irrigation_communication_register)
        if last_communicated_irrigation is not None:
            next_irrigationid = last_communicated_irrigation.irrigationid+1
        else:
            next_irrigationid = 0
        li_not_communicated = IrrigationData.getsince_in_file(fn_irrigation_data, next_irrigationid)
        return (last_irrigation_cycle, last_communicated_irrigation, li_not_communicated)

    @staticmethod
    def load_not_communicated_deepcheck(fn_irrigation_data, fn_irrigation_communication_register):
        last_irrigation_cycle = IrrigationData.getlast_in_file(fn_irrigation_data)
        last_communicated_irrigation = IrrigationDataCommunication.getlast_in_file(fn_irrigation_communication_register)
        li_not_communicated = []
        # Load communicated irrigations identifiers
        aux = IrrigationDataCommunication.load_from_file(fn_irrigation_communication_register)
        li_communicated_id = [item.irrigationid for item in aux]

        # Load irrigations data
        liIrrigations = IrrigationData.load_from_file(fn_irrigation_data)            
        di_irrigations = {item.irrigationid: item for item in liIrrigations}

        # Search which irrigations have already been communicated
        for irrigationid in di_irrigations:
            if irrigationid not in li_communicated_id:
                item = di_irrigations[irrigationid]
                li_not_communicated.append(item)

        # Release memory
        del aux
        del li_communicated_id
        del liIrrigations
        del di_irrigations
        gc.collect()
        return (last_irrigation_cycle, last_communicated_irrigation, li_not_communicated)


class IrrigationDataCommunication(NsDataClass):

    KEY_ID = "irrigationid" # Irrigation Id -> int sequence
    
    fields = (KEY_ID,)
    packstring = 'i'
    packlength = struct.calcsize(packstring) #bytes 4

    def __init__(self, irrigationid=0):
        super(IrrigationDataCommunication, self).__init__(alarm=0)
        self.irrigationid = irrigationid



    def __repr__(self):
        return "IrrigationDataCommunication('{irrigationid}')".format(
            irrigationid=self.irrigationid)

    def to_dict(self):
        d = {
            IrrigationData.KEY_IRRIGATIONID: self.irrigationid,
        }
        return d

    def from_dict(self, d):
        self.irrigationid = d[IrrigationData.KEY_IRRIGATIONID]


    @staticmethod
    def test1():
        import machine
        
        obj = IrrigationDataCommunication(3)
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("IrrigationDataCommunication Original -> {o}".format(o=repr(obj)))
        print ("IrrigationDataCommunication Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = IrrigationDataCommunication()
        sw.read(p, obj2)
        print ("IrrigationDataCommunication Unpacked -> {u}".format(u=repr(obj2)))

    @staticmethod
    def print_communicated_irrigation_cycles():
        import planter_pinout as PINOUT
        last_irrigation = IrrigationDataCommunication.getlast_in_file(PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN)
        li = IrrigationDataCommunication.load_from_file(PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN)

        if li is not None:
            for i in li:
                print(i)