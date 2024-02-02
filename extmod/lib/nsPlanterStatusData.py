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

_logger = logging.getLogger("PlanterStatusData")
_logger.setLevel(logging.WARNING)

class PlanterStatusData(NsDataClass):

    KEY_TS = "ts"
    KEY_PUMP_ON = "pump_on"
    KEY_POWER_3V_ON = "power_3v_on"
    KEY_POWER_5V_ON = "power_5v_on"
    KEY_POWER_12V_ON = "power_12v_on"
    KEY_LEVEL_LOW = "level_low"
    KEY_DOOR_OPEN = "door_open"
    KEY_SOIL_MOISTURE_VWC = "soil_moisture_vwc"
    KEY_SOIL_TEMPERATURE_C = "soil_temperature_c"
    KEY_FLOW_LPM = "flow_lpm"
    KEY_RAIN_MMPH = "rain_mmph"

    KEY_VPV = "vpv"
    KEY_IPV = "ipv"
    KEY_VBATT = "vbatt"
    KEY_IBATT = "ibatt"
    KEY_VPUMP = "vpump"
    KEY_IPUMP = "ipump"

    KEY_DIO = "dio"
    KEY_ALARM = "alarm"
    
    KEY_SW_VERSION = "sw_ver"
    KEY_FW_VERSION = "fw_ver"

    ALARM_BIT_BATT_LOW = 0x0001              # Alarm if battery voltage below 10.75V
    ALARM_BIT_BATT_DEAD = 0x0002             # Alarm if battery voltage below 10.4V
    ALARM_BIT_PV = 0x0004                    # Alarm if photovoltaic panel voltage below 20mV

    ALARM_BIT_PUMP_V = 0x0008                # Alarm if pump voltage below (batt voltage - 2V) when pump is ON
    ALARM_BIT_PUMP_I = 0x0010                # Alarm if pump current below 0.9A when pump is ON after soft-start
    ALARM_BIT_PUMP_A = 0x0020                # Alarm if pump current or voltage are not zero when pump is OFF

    ALARM_BIT_FLOWMETER_NONE = 0x0040        # Alarm if there is no flow pulses when pump is ON
    ALARM_BIT_FLOWMETER_INF = 0x0080         # Alarm if the number of flow pulses is too high compared to the pump-on time

    ALARM_BIT_SM = 0x0100                    # Alarm if cannot read main soil moisture sensor after power-on delay and retry threshold
    ALARM_BIT_WATERLEVEL_LOW = 0x0200        # Alarm if water level sensor indicates low level
    ALARM_BIT_DOOR_OPEN = 0x0400             # Alarm if the door is open
    ALARM_BIT_ACCEL = 0x0800                 # Alarm if the accelerometer cannot be read
    ALARM_BIT_POWERMONITOR = 0x1000          # Alarm if the power monitor cannot be read (INA)
    ALARM_BIT_WATERLEVEL_SENSOR = 0x2000     # Alarm if water level sensor cannot be detected

    ALARM_BIT_WIFI = 0x4000                  # Alarm if cannot connect to wifi after several trials
    ALARM_BIT_GPRS = 0x8000                  # Alarm if cannot connect GPRS after several trials



    fields = (KEY_TS, KEY_DIO,
                KEY_SOIL_MOISTURE_VWC, KEY_SOIL_TEMPERATURE_C, KEY_FLOW_LPM, KEY_RAIN_MMPH,
                KEY_VPV, KEY_IPV, KEY_VBATT, KEY_IBATT, 
                KEY_VPUMP, KEY_IPUMP, 
                KEY_ALARM)
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    # sw_ver string is 8 char: xx.xx.xx
    # fw_ver string is 8 char: xx.xx.xx
    packstring = '23sBffffffffffi8s8s'
    packlength = struct.calcsize(packstring) # 84 #bytes

    @property
    def dio(self):
        r = (0x01 if self.pump_on else 0x00) | \
            (0x02 if self.power_3v_on else 0x00) | \
            (0x04 if self.power_5v_on else 0x00) | \
            (0x08 if self.power_12v_on else 0x00) | \
            (0x10 if self.level_low else 0x00) | \
            (0x20 if self.door_open else 0x00)
        return r

    @dio.setter
    def dio(self, v):
        self.pump_on = (v & 0x01) == 0x01
        self.power_3v_on = (v & 0x02) == 0x02
        self.power_5v_on = (v & 0x04) == 0x04
        self.power_12v_on = (v & 0x08) == 0x08
        self.level_low = (v & 0x10) == 0x10
        self.door_open = (v & 0x20) == 0x20

        self.alarm_waterlevel_low = self.level_low
        self.alarm_door_open = self.door_open

    @property
    def ts(self):
        return self._ts

    @ts.setter
    def ts(self, v):
        self._ts = timetools.tostr(v)

    @property
    def alarm_batt_low(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_BATT_LOW) == PlanterStatusData.ALARM_BIT_BATT_LOW

    @alarm_batt_low.setter
    def alarm_batt_low(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_BATT_LOW, v)
        if r and v:
            _logger.warning("BATT LOW")


    @property
    def alarm_batt_dead(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_BATT_DEAD) == PlanterStatusData.ALARM_BIT_BATT_DEAD


    @alarm_batt_dead.setter
    def alarm_batt_dead(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_BATT_DEAD, v)
        if r and v:
            _logger.warning("BATT DEAD")

    @property
    def alarm_pv(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_PV) == PlanterStatusData.ALARM_BIT_PV

    @alarm_pv.setter
    def alarm_pv(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_PV, v)
        if r and v:
            _logger.warning("PV DEAD")

    @property
    def alarm_pump_v(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_PUMP_V) == PlanterStatusData.ALARM_BIT_PUMP_V

    @alarm_pump_v.setter
    def alarm_pump_v(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_PUMP_V, v)
        if r and v:
            _logger.warning("PUMP VOLTAGE LOW")

    @property
    def alarm_pump_i(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_PUMP_I) == PlanterStatusData.ALARM_BIT_PUMP_I

    @alarm_pump_i.setter
    def alarm_pump_i(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_PUMP_I, v)
        if r and v:
            _logger.warning("PUMP CURRENT LOW")

    @property
    def alarm_pump_a(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_PUMP_A) == PlanterStatusData.ALARM_BIT_PUMP_A

    @alarm_pump_a.setter
    def alarm_pump_a(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_PUMP_A, v)
        if r and v:
            _logger.warning("PUMP IS ACTIVE OUTSIDE OF IRRIGATION CYCLE")

    @property
    def alarm_flowmeter_none(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_FLOWMETER_NONE) == PlanterStatusData.ALARM_BIT_FLOWMETER_NONE

    @alarm_flowmeter_none.setter
    def alarm_flowmeter_none(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_FLOWMETER_NONE, v)
        if r and v:
            _logger.warning("NO FLOW DETECTED")

    @property
    def alarm_flowmeter_inf(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_FLOWMETER_INF) == PlanterStatusData.ALARM_BIT_FLOWMETER_INF

    @alarm_flowmeter_inf.setter
    def alarm_flowmeter_inf(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_FLOWMETER_INF, v)
        if r and v:
            _logger.warning("TOO MANY FLOW PULSES")

    @property
    def alarm_sm(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_SM) == PlanterStatusData.ALARM_BIT_SM

    @alarm_sm.setter
    def alarm_sm(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_SM, v)
        if r and v:
            _logger.warning("SOIL MOISTURE SENSOR CANNOT BE READ")

    @property
    def alarm_waterlevel_low(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_WATERLEVEL_LOW) == PlanterStatusData.ALARM_BIT_WATERLEVEL_LOW

    @alarm_waterlevel_low.setter
    def alarm_waterlevel_low(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_WATERLEVEL_LOW, v)
        if r and v:
            _logger.warning("WATER LEVEL LOW")

    @property
    def alarm_door_open(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_DOOR_OPEN) == PlanterStatusData.ALARM_BIT_DOOR_OPEN

    @alarm_door_open.setter
    def alarm_door_open(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_DOOR_OPEN, v)
        if r and v:
            _logger.warning("DOOR IS OPEN")

    @property
    def alarm_accel(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_ACCEL) == PlanterStatusData.ALARM_BIT_ACCEL

    @alarm_accel.setter
    def alarm_accel(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_ACCEL, v)
        if r and v:
            _logger.warning("CANNOT READ ACCELEROMETER")

    @property
    def alarm_powermonitor(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_POWERMONITOR) == PlanterStatusData.ALARM_BIT_POWERMONITOR

    @alarm_powermonitor.setter
    def alarm_powermonitor(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_POWERMONITOR, v)
        if r and v:
            _logger.warning("CANNOT READ POWER MONITOR")

    @property
    def alarm_wifi(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_WIFI) == PlanterStatusData.ALARM_BIT_WIFI

    @alarm_wifi.setter
    def alarm_wifi(self, v):
        r=self.update_alarm(PlanterStatusData.ALARM_BIT_WIFI, v)
        if r and v:
            _logger.warning("CANNOT CONNECT TO WIFI")

    @property
    def alarm_gprs(self):
        return (self.alarm & PlanterStatusData.ALARM_BIT_GPRS) == PlanterStatusData.ALARM_BIT_GPRS

    @alarm_gprs.setter
    def alarm_gprs(self, v):
        r = self.update_alarm(PlanterStatusData.ALARM_BIT_GPRS, v)
        if r and v:
            _logger.warning("CANNOT CONNECT TO INTERNET USING PPP THROUGH GPRS")


    def __init__(self, ts='', pump_on=False, power_3v_on=False, power_5v_on=False, power_12v_on=False
                , level_low=False, door_open=False
                , soil_moisture_vwc=0, soil_temperature_c=0
                , flow_lpm=0, rain_mmph=0
                , vpv=0, ipv=0
                , vbatt=0, ibatt=0
                , vpump=0, ipump=0, alarm=0
                , sw_ver='', fw_ver=''):
        super(PlanterStatusData, self).__init__(alarm)
        #self.ts = timetools.totimestamp(ts)
        self._ts = timetools.tostr(ts)
        self.pump_on = pump_on
        self.power_3v_on = power_3v_on
        self.power_5v_on = power_5v_on
        self.power_12v_on = power_12v_on
        self.level_low = level_low
        self.door_open = door_open
        self.soil_moisture_vwc = soil_moisture_vwc
        self.soil_temperature_c = soil_temperature_c
        self.flow_lpm = flow_lpm
        self.rain_mmph = rain_mmph
        self.vpv = vpv
        self.ipv = ipv
        self.vbatt = vbatt
        self.ibatt = ibatt
        self.vpump = vpump
        self.ipump = ipump
        self.alarm = alarm
        self.water_level_sensor_detected = False
        self.sw_ver = sw_ver
        self.fw_ver = fw_ver


    def __repr__(self):
        return "PlanterStatusData('{ts}',{pump_on},{power_3v_on},{power_5v_on},{power_12v_on},{level_low},{door_open},{soil_moisture_vwc},{soil_temperature_c},{flow_lpm},{rain_mmph},{vpv},{ipv},{vbatt},{ibatt},{vpump},{ipump},{alarm},{sw_ver},{fw_ver})".format(
            ts=self.ts, pump_on=self.pump_on, power_3v_on=self.power_3v_on, power_5v_on=self.power_5v_on, power_12v_on=self.power_12v_on,
            level_low=self.level_low, door_open=self.door_open, soil_moisture_vwc=self.soil_moisture_vwc, soil_temperature_c=self.soil_temperature_c,
            flow_lpm=self.flow_lpm, rain_mmph=self.rain_mmph, vpv=self.vpv, ipv=self.ipv,
            vbatt=self.vbatt, ibatt=self.ibatt, vpump=self.vpump, ipump=self.ipump, alarm=self.alarm,
            sw_ver=self.sw_ver, fw_ver=self.fw_ver)

    def to_dict(self):
        d = {
            PlanterStatusData.KEY_TS : self.ts,
            PlanterStatusData.KEY_PUMP_ON : self.pump_on,
            PlanterStatusData.KEY_POWER_3V_ON : self.power_3v_on,
            PlanterStatusData.KEY_POWER_5V_ON : self.power_5v_on,
            PlanterStatusData.KEY_POWER_12V_ON : self.power_12v_on,
            PlanterStatusData.KEY_LEVEL_LOW : self.level_low,
            PlanterStatusData.KEY_DOOR_OPEN : self.door_open,
            PlanterStatusData.KEY_SOIL_MOISTURE_VWC : round(self.soil_moisture_vwc,2) if self.soil_moisture_vwc is not None else 0,
            PlanterStatusData.KEY_SOIL_TEMPERATURE_C : round(self.soil_temperature_c,2) if self.soil_temperature_c is not None else 0,
            PlanterStatusData.KEY_FLOW_LPM : self.flow_lpm,
            PlanterStatusData.KEY_RAIN_MMPH : self.rain_mmph,

            PlanterStatusData.KEY_VPV : self.vpv,
            PlanterStatusData.KEY_IPV : self.ipv,
            PlanterStatusData.KEY_VBATT : self.vbatt,
            PlanterStatusData.KEY_IBATT : self.ibatt,
            PlanterStatusData.KEY_VPUMP : self.vpump,
            PlanterStatusData.KEY_IPUMP : self.ipump,
            PlanterStatusData.KEY_ALARM : self.alarm,
            PlanterStatusData.KEY_SW_VERSION : self.sw_ver,
            PlanterStatusData.KEY_FW_VERSION: self.fw_ver
        }
        return d

    def to_bin(self):

        for f in self.fields:
            v = getattr(self,f)
            if v is None:
                _logger.debug("nsPlanterStatusData - Set field {f} to 0 because it is None".format(f=f))
                setattr(self, f, 0)

        sw = nsClassWriter.StructWriter()
        p = sw.write(self)
        return p


    def from_dict(self, d):
        if PlanterStatusData.KEY_TS in d:
            self.ts = d[PlanterStatusData.KEY_TS]
        if PlanterStatusData.KEY_PUMP_ON in d:
            self.pump_on = d[PlanterStatusData.KEY_PUMP_ON]
        if PlanterStatusData.KEY_POWER_3V_ON in d:
            self.power_3v_on = d[PlanterStatusData.KEY_POWER_3V_ON]
        if PlanterStatusData.KEY_POWER_5V_ON in d:
            self.power_5v_on = d[PlanterStatusData.KEY_POWER_5V_ON]
        if PlanterStatusData.KEY_POWER_12V_ON in d:
            self.power_12v_on = d[PlanterStatusData.KEY_POWER_12V_ON]
        if PlanterStatusData.KEY_LEVEL_LOW in d:
            self.level_low = d[PlanterStatusData.KEY_LEVEL_LOW]
        if PlanterStatusData.KEY_DOOR_OPEN in d:            
            self.door_open = d[PlanterStatusData.KEY_DOOR_OPEN]
        if PlanterStatusData.KEY_SOIL_MOISTURE_VWC in d:
            self.soil_moisture_vwc = d[PlanterStatusData.KEY_SOIL_MOISTURE_VWC]
        if PlanterStatusData.KEY_SOIL_TEMPERATURE_C in d:
            self.soil_temperature_c = d[PlanterStatusData.KEY_SOIL_TEMPERATURE_C]
        if PlanterStatusData.KEY_FLOW_LPM in d:
            self.flow_lpm = d[PlanterStatusData.KEY_FLOW_LPM]
        if PlanterStatusData.KEY_RAIN_MMPH in d:
            self.rain_mmph = d[PlanterStatusData.KEY_RAIN_MMPH]
        if PlanterStatusData.KEY_VPV in d:
            self.vpv = d[PlanterStatusData.KEY_VPV]
        if PlanterStatusData.KEY_IPV in d:
            self.ipv = d[PlanterStatusData.KEY_IPV]
        if PlanterStatusData.KEY_VBATT in d:
            self.vbatt = d[PlanterStatusData.KEY_VBATT]
        if PlanterStatusData.KEY_IBATT in d:
            self.ibatt = d[PlanterStatusData.KEY_IBATT]
        if PlanterStatusData.KEY_VPUMP in d:
            self.vpump = d[PlanterStatusData.KEY_VPUMP]
        if PlanterStatusData.KEY_IPUMP in d:
            self.ipump = d[PlanterStatusData.KEY_IPUMP]
        if PlanterStatusData.KEY_ALARM in d:
            self.alarm = d[PlanterStatusData.KEY_ALARM]
        if PlanterStatusData.KEY_SW_VERSION in d:
            self.sw_ver = d[PlanterStatusData.KEY_SW_VERSION]
        if PlanterStatusData.KEY_FW_VERSION in d:
            self.fw_ver = d[PlanterStatusData.KEY_FW_VERSION]

    def from_bin(self, p):
        sw = nsClassWriter.StructWriter()
        sw.read(p, self)

    @staticmethod
    def test():
        import machine

        rtc = machine.RTC()
        dt = rtc.datetime()
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        obj = PlanterStatusData(ts_str, False, True, True, True, False, False, 23.1, 25.4, 3.4, 0.0, 18.4, 0.7, 12.5, 0.069, 12.1, 1.3,'aa.bb.cc','dd.ee.ff')
        sw = nsClassWriter.StructWriter()
        p = sw.write(obj)
        print ("PlanterStatusData Original -> {o}".format(o=repr(obj)))
        print ("PlanterStatusData Packed -> {p} -> {l} bytes".format(p=str(p),l=len(p)))
        obj2 = PlanterStatusData()
        sw.read(p, obj2)
        print ("PlanterStatusData Unpacked -> {u}".format(u=repr(obj2)))





