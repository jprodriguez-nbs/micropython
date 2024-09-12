import logging
import esp32
import machine
import os
import utime
import ujson
import sys
import ure
import gc

from micropython import const


import planter_pinout as PINOUT
import planter.config as CFG

import power_monitor as power_monitor
import colors
import tools

from nsPlanterStatusData import PlanterStatusData
from nsIrrigationData import IrrigationData, IrrigationDataCommunication
from nsRainData import RainData, RainDataCommunication
from networkmgr import NetworkMgr
import timetools as timetools


try:
    import ubinascii
    from ubinascii import a2b_base64 as b64decode
    from ubinascii import b2a_base64 as b64encode
except:
    import base64
    from base64 import b64decode as b64decode
    from base64 import b64encode as b64encode

STATUS_KEY_ID = "id"
STATUS_KEY_START = IrrigationData.KEY_START
STATUS_KEY_END = IrrigationData.KEY_END
STATUS_KEY_START_MS = "start_ms"
STATUS_KEY_END_MS = "end_ms"
STATUS_KEY_DURATION = IrrigationData.KEY_DURATION
STATUS_KEY_PULSES = IrrigationData.KEY_PULSES
STATUS_KEY_VOL_L = IrrigationData.KEY_VOL_L
STATUS_KEY_CE_MWH = IrrigationData.KEY_CE_MWH
STATUS_KEY_INITIAL_SOIL_MOISTURE_VWC = IrrigationData.KEY_INITIAL_SOIL_MOISTURE_VWC
STATUS_KEY_FINAL_SOIL_MOISTURE_VWC = IrrigationData.KEY_FINAL_SOIL_MOISTURE_VWC


STATUS_KEY_STATUS = "status"
STATUS_KEY_TS = "ts"
STATUS_KEY_IRRIGATION_CYCLES = "irrigation_cycles"
STATUS_KEY_POWER_MEASURES = "power_measures"

STATUS_KEY_POWER = "power"
STATUS_KEY_LAST_UPDATE_CHECK = "last_update_check"



EVENT_KEY_TYPE = "idevent"
EVENT_KEY_VALUE = "value"
EVENT_KEY_EXTRADATA = "extradata"


DISPLAY_TIMEOUT_SECONDS = const(60)

MACHINE_IRQ_WAKE = {
    #machine.IDLE: "IDLE",
    machine.SLEEP: "SLEEP",
    machine.DEEPSLEEP: "DEEPSLEEP",
}


MACHINE_RESERT_CAUSES = {
    machine.PWRON_RESET: "PWRON_RESET",
    machine.HARD_RESET: "HARD_RESET",
    machine.WDT_RESET: "WDT_RESET",
    machine.DEEPSLEEP_RESET: "DEEPSLEEP_RESET",
    machine.SOFT_RESET: "SOFT_RESET",
}

MACHINE_WAKE_UP_REASONS = {
    0: "RESET",
    1: "WAKE 1",
    machine.EXT0_WAKE: "EXT0_WAKE",
    machine.EXT1_WAKE: "EXT1_WAKE",
    machine.PIN_WAKE: "PIN_WAKE",
    machine.TIMER_WAKE: "TIMER_WAKE",
    machine.TOUCHPAD_WAKE: "TOUCHPAD_WAKE",
    machine.ULP_WAKE: "ULP_WAKE",
}


class PlanterEvents():

    VALUE_LOW = 0
    VALUE_NORMAL = 1
    VALUE_HIGH = 2

    STATUS_OFF = 0 # Also means disabled, finished
    STATUS_ON = 1 # Also means enabled, started

    STATUS_DISABLED = STATUS_OFF
    STATUS_ENABLED = STATUS_ON

    STATUS_FINISHED = STATUS_OFF
    STATUS_STARTED = STATUS_ON
    STATUS_CHANGED = 3

    # INPUTS
    Flow = "flow"                      # Indicates if flow is detected (1)
    Rain = "rain"                      # Indicates if rain is detected (1)
    Door_Open = "door"                 # Indicates if the door is open (1)
    Impact_Detected = "impact"         # Indicates that an impact has been detected (1)
    Water_Level = "water_level"        # Indicates if the water level is LOW (0) or NORMAL (1)
    Soil_Moisture = "soil_moisture"    # Indicates if the soil moisture is LOW (0) or NORMAL (1)
    Power_Monitor = "power_monitor"    # Indicates if there is any problem with the power monitor

    # OUTPUTS
    Pump = "pump"                  # Indicates if the pump power line is enabled
    IO_Interface = "io"            # Indicates if IO level shifter output is enabled
    Load_Switch_5v = "load_5v"     # Indicates if the 5V load power line is enabled
    Load_Switch_12v = "load_12v"   # Indicates if the 12V load power line is enabled

    # POWER
    Power_Line_5v = "ps_5v"     # Indicates if 5V is detected in the 5V power supply line
    Power_Line_12v = "ps_12v"   # Indicates if 12V is detected in the 12V power supply line

    # CYCLES
    Wake = "wake"

    # Alarms
    Alarm = "alarm"
    Water_Level_Sensor_Detected = "water_level_sensor_detected"    # Indicates if the water level sensor has been DETECTED (1) or has FAILED (0)

    Irrigation_Decission ="irrigation_decission" # Indicates that a decission about start or skip an irrigation has taken place

    ID_START_IRRIGATION = 1
    ID_RAIN_INTENSITY = 10 # Decided to skip irrigation because of intensity
    ID_RAIN_PROB = 11 # Decided to skip irrigation because of probability
    ID_BATTERY_VOLT = 12 # Decided to skip irrigation because battery voltage is too low
    


class PlanterStatus():

    PAGE_OFF = const(0)
    PAGE_POWER_12V = const(1)
    PAGE_POWER_5V = const(2)
    PAGE_SOIL_MOISTURE = const(3)
    PAGE_PUMP = const(4)
    PAGE_WIFI = const(5)
    PAGE_FS = const(6)
    MAX_PAGE_NUMBER = const(6)


    @property
    def data(self):
        return self._status_data

    def update_alarm(self, alarm_bit, value):
        self._status_data.update_alarm(alarm_bit, value)

    @property
    def pump_on(self):
        return self._status_data.pump_on

    def set_pump_status(self, value, extradata):
        if self._status_data.pump_on != value:
            self._status_data.pump_on = value
            if value:
                self.add_event(PlanterEvents.Pump, PlanterEvents.STATUS_ON, extradata)
            else:
                self.add_event(PlanterEvents.Pump, PlanterEvents.STATUS_OFF, extradata)

    def set_pump_details(self, details):
        self._pump_details = details

    @property
    def load_3v_on(self):
        return self._status_data.power_3v_on

    @load_3v_on.setter
    def load_3v_on (self, value):
        if self._status_data.power_3v_on != value:
            self._status_data.power_3v_on = value
            # if value:
            #     self.add_event(PlanterEvents.IO_Interface, PlanterEvents.STATUS_ENABLED)
            # else:
            #     self.add_event(PlanterEvents.IO_Interface, PlanterEvents.STATUS_DISABLED)


    @property
    def load_5v_on(self):
        return self._status_data.power_5v_on

    @load_5v_on.setter
    def load_5v_on(self, value):
        if self._status_data.power_5v_on != value:
            self._status_data.power_5v_on = value
            # if value:
            #     self.add_event(PlanterEvents.Load_Switch_5v, PlanterEvents.STATUS_ON)
            # else:
            #     self.add_event(PlanterEvents.Load_Switch_5v, PlanterEvents.STATUS_OFF)

    @property
    def load_12v_on(self):
        return self._status_data.power_12v_on

    @load_12v_on.setter
    def load_12v_on(self, value):
        if self._status_data.power_12v_on != value:
            self._status_data.power_12v_on = value
            # if value:
            #     self.add_event(PlanterEvents.Load_Switch_12v, PlanterEvents.STATUS_ON)
            # else:
            #     self.add_event(PlanterEvents.Load_Switch_12v, PlanterEvents.STATUS_OFF)

    @property
    def water_level_sensor_detected(self):
        return self._status_data.water_level_sensor_detected

    @water_level_sensor_detected.setter
    def water_level_sensor_detected(self, value):
        # If the sensor detects water, the output digital value is False
        # If the sensor does not detect water, the output digital value is True
        # If there is no sensor, the pullup resistor sets a True value
        new_water_level_sensor_detected = value is True
        if self._status_data.water_level_sensor_detected != new_water_level_sensor_detected:
            self._status_data.water_level_sensor_detected = new_water_level_sensor_detected
            if self._status_data.water_level_sensor_detected is True:
                self.add_event(PlanterEvents.Water_Level_Sensor_Detected, PlanterEvents.VALUE_NORMAL,"Normal")
                self.update_alarm(PlanterStatusData.ALARM_BIT_WATERLEVEL_SENSOR, False)
            else:
                self.add_event(PlanterEvents.Water_Level_Sensor_Detected, PlanterEvents.VALUE_LOW, "Failed")
                self.update_alarm(PlanterStatusData.ALARM_BIT_WATERLEVEL_SENSOR, True)

    @property
    def level_low(self):
        return self._status_data.level_low

    @level_low.setter
    def level_low(self, value):
        # If the sensor detects water, the output digital value is False
        # If the sensor does not detect water, the output digital value is True
        # If there is no sensor, the pullup resistor sets a True value
        new_level_low = value is True
        if self._status_data.level_low != new_level_low:
            ts_now = utime.time()
            if self._ts_last_level_change is None or ((ts_now-self._ts_last_level_change)>1):
                # we can debounce by time because we read io periodically
                self._ts_last_level_change = ts_now
                self._status_data.level_low = new_level_low
                if self._status_data.level_low is False:
                    self.add_event(PlanterEvents.Water_Level, PlanterEvents.VALUE_NORMAL,"Normal")
                    self.update_alarm(PlanterStatusData.ALARM_BIT_WATERLEVEL_LOW, False)
                else:
                    self.add_event(PlanterEvents.Water_Level, PlanterEvents.VALUE_LOW, "Low")
                    self.update_alarm(PlanterStatusData.ALARM_BIT_WATERLEVEL_LOW, True)

    @property
    def door_open(self):
        return self._status_data.door_open

    @door_open.setter
    def door_open(self, value):
        if self._status_data.door_open != value:
            self._status_data.door_open = value
            if value:
                self.add_event(PlanterEvents.Door_Open, PlanterEvents.STATUS_ON,"Open")
                self.update_alarm(PlanterStatusData.ALARM_BIT_DOOR_OPEN, True)
            else:
                self.add_event(PlanterEvents.Door_Open, PlanterEvents.STATUS_OFF, "Closed")
                self.update_alarm(PlanterStatusData.ALARM_BIT_DOOR_OPEN, False)

    @property
    def soil_moisture_data_available(self):
        return self._soil_moisture_data_available

    @soil_moisture_data_available.setter
    def soil_moisture_data_available(self, value):
        if self._soil_moisture_data_available != value:
            self._logger.info("soil_moisture_data_available changed from {p} to {n}".format(p=self._soil_moisture_data_available, n=value))
            self._soil_moisture_data_available = value
            if value is True:
                self._status_data.alarm_sm = False

    @property
    def soil_moisture_read_trial(self):
        return self._soil_moisture_read_trial

    @soil_moisture_read_trial.setter
    def soil_moisture_read_trial(self, value):
        if self._soil_moisture_read_trial != value:
            #self._logger.debug("soil_moisture_read_trial changed from {p} to {n}".format(p=self._soil_moisture_read_trial, n=value))
            self._soil_moisture_read_trial = value
            if value > 4:
                self._status_data.alarm_sm = True
            else:
                self._status_data.alarm_sm = False

    @property
    def soil_moisture_th(self):
        r = 23.0
        try:
            r = float(self.params[CFG.K_MOISTURE_LOW_TH])
        except:
            pass
        return r

    @property
    def soil_moisture_vwc(self):
        return self._status_data.soil_moisture_vwc

    @soil_moisture_vwc.setter
    def soil_moisture_vwc(self, value):
        if self._status_data.soil_moisture_vwc != value:
            moisture_low_th = self.soil_moisture_th

            new_soil_moisture_status = PlanterEvents.VALUE_NORMAL
            if value < moisture_low_th:
                new_soil_moisture_status = PlanterEvents.VALUE_LOW
            else:
                new_soil_moisture_status = PlanterEvents.VALUE_NORMAL

            if self._soil_moisture_status != new_soil_moisture_status:
                self.add_event(PlanterEvents.Soil_Moisture, new_soil_moisture_status, "{v:5.2f} %".format(v=value))
                self._soil_moisture_status = new_soil_moisture_status

            self._status_data.soil_moisture_vwc = value
            #self._soil_moisture_data_available = True

    @property
    def soil_temperature_c(self):
        return self._status_data.soil_temperature_c

    @soil_temperature_c.setter
    def soil_temperature_c(self, value):
        if self._status_data.soil_temperature_c != value:
            self._status_data.soil_temperature_c = value
            #self._soil_moisture_data_available = True

    @property
    def flow_lpm(self):
        return self._status_data.flow_lpm

    @flow_lpm.setter
    def flow_lpm(self, value):
        if self._status_data.flow_lpm != value:
            abs_dif = abs(self._status_data.flow_lpm-value)
            if ((self._status_data.flow_lpm == 0) and (value != 0)):
                self.add_event(PlanterEvents.Flow, PlanterEvents.STATUS_STARTED, "STARTED - {f:5.2f} lpm".format(f=value))
            elif (self._status_data.flow_lpm != 0) and (value == 0):
                self.add_event(PlanterEvents.Flow, PlanterEvents.STATUS_FINISHED,  "FINISHED - {r:5.2f} lpm".format(r=value))
            elif abs_dif>0.2:
                self.add_event(PlanterEvents.Flow, PlanterEvents.STATUS_CHANGED,  "CHANGED - {r:5.2f} lpm".format(r=value))
            self._status_data.flow_lpm = value

    @property
    def rain_mmph(self):
        return self._status_data.rain_mmph

    @rain_mmph.setter
    def rain_mmph(self, value):
        if self._status_data.rain_mmph != value:
            abs_dif = abs(self._status_data.rain_mmph-value)
            if (self._status_data.rain_mmph == 0) and (value != 0):
                self.add_event(PlanterEvents.Rain, PlanterEvents.STATUS_STARTED,  "STARTED - {r:5.2f} mmph".format(r=value))
            elif (self._status_data.rain_mmph != 0) and (value == 0):
                self.add_event(PlanterEvents.Rain, PlanterEvents.STATUS_FINISHED,  "FINISHED - {r:5.2f} mmph".format(r=value))
            elif abs_dif>0.2:
                self.add_event(PlanterEvents.Rain, PlanterEvents.STATUS_CHANGED,  "CHANGED - {r:5.2f} mmph".format(r=value))
            self._status_data.rain_mmph = value


    @property
    def pulse_count(self):
        return self._pulse_count

    @pulse_count.setter
    def pulse_count(self, value):
        self._pulse_count = value

    @property
    def pps(self):
        return self._pps

    @pps.setter
    def pps(self, value):
        self._pps = value


    @property
    def ts_last_pump_start(self):
        return self._ts_last_pump_start

    @ts_last_pump_start.setter
    def ts_last_pump_start(self, value):
        self._ts_last_pump_start = value


    @property
    def ts_last_pump_stop(self):
        return self._ts_last_pump_stop

    @ts_last_pump_stop.setter
    def ts_last_pump_stop(self, value):
        self._ts_last_pump_stop = value


    @property
    def ts_last_status_post(self):
        return self._ts_last_status_post

    @ts_last_status_post.setter
    def ts_last_status_post(self, value):
        self._ts_last_status_post = value


    @property
    def ts_last_button1_pressed_ticks_ms(self):
        return self._ts_last_button1_pressed_ticks_ms


    def set_di(self, di_values):
        hasChanged = False
        (f, r, d, l, i1, i2, b1, nsmbalert, socalert, a, b) = di_values
        

        if self.has_mcp is False:
            # Cannot read mcp -> fix values
            b1 = True # Button is not pressed
            d = False # The door is not open
            l = False # Water level is not low
            i1 = False # Not int
            i2 = False # Not int

        if di_values != self._last_di_values:
            self._last_di_values = di_values
            hasChanged = True
            f_str = "Flow: {pps} [pulses/s] -> {flow_lpm} L/min -- MCP = {mcp}, A = {a:08b}  B = {b:08b}, r={r}, d open={d}, l_low={l}, i1={i1}, i2={i2}, b1={b1}, nsmbalert={nsmbalert}, socalert={socalert}".format(
                pps = self._pps, flow_lpm=self._status_data.flow_lpm, 
                mcp = self.has_mcp,
                a=a, b=b, r=r, d=d, l=l, i1=i1, i2=i2, b1=b1,
                nsmbalert=nsmbalert, socalert=socalert)
            self._logger.info(f_str)

        self.door_open = d
        self.level_low = l

        if (self._button1 is True) and (b1 is False):
            self.inc_display_page()
            # Increase timestamp
            self._ts_last_button1_pressed_ticks_ms = utime.ticks_ms()
        self._button1 = b1

        return hasChanged


    @property
    def static_config(self):
        return self._static_config

    @static_config.setter
    def static_config(self, value):
        self._static_config = value
        self.update_url()


    #
    #
    # IRRIGATION
    #
    #

    def irrigation_cycles(self):
        """
        [
            {
                "id":0,
                "start": "",
                "end": "",
                "duration": 0,
                "pulses": "",
                "vol_l": 0,
                "ce_mwh": 0,
                "vbatt": 0,
                "vpump": 0,
                "ipump": 0,
                "initial_sm_vwc": 0,
                "final_sm_vwc": 0
            }
        ]
        """
        return self._irrigation_cycles

    def add_irrigation_cycle(self, cycle_data):
        if cycle_data is not None:
            if len(self._irrigation_cycles) < 100:
                self._irrigation_cycles.append(cycle_data)

    def clear_irrigation_cycles(self, mark_sent=False):
        if mark_sent:
            try:
                l = []
                for ir in self._irrigation_cycles:
                    c = IrrigationDataCommunication(ir.irrigationid)
                    l.append(c)
                IrrigationDataCommunication.append_to_file(PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN, l)
            except Exception as ex:
                self._logger.exc(ex,"status.clear_irrigation_cycles exception: {e}".format(e=str(ex)))


        self._irrigation_cycles.clear()

    def current_irrigation_cycle_start_ms(self):
        if self._current_irrigation_cycle:
            return self._current_irrigation_cycle[STATUS_KEY_START_MS]
        return None

    def current_irrigationid(self):
        if self._current_irrigation_cycle:
            return self._current_irrigation_cycle[STATUS_KEY_ID]
        return None

    def start_irrigation_cycle(self):
        if self._current_irrigation_cycle is not None:
            # This is an error
            print("Error: current irrigation cycle is not None")

        irrigationid = 0
        if self._last_irrigation_cycle is not None:
            irrigationid = int(self._last_irrigation_cycle.irrigationid) + 1

        self._current_irrigation_cycle = {
            STATUS_KEY_ID: irrigationid,
            STATUS_KEY_START: self.ts(),
            STATUS_KEY_START_MS: utime.ticks_ms(),
            STATUS_KEY_END: None,
            STATUS_KEY_END_MS: None,
            STATUS_KEY_PULSES: 0,
            STATUS_KEY_VOL_L: None,
            STATUS_KEY_CE_MWH: None,
            STATUS_KEY_INITIAL_SOIL_MOISTURE_VWC: self.soil_moisture_vwc
        }

    def end_irrigation_cycle(self, pulses, vol_l, ce_mwh, vbatt, vpump, ipump):
        try:
            c = self._current_irrigation_cycle
            if c is not None:

                soil_moisture_vwc=self.soil_moisture_vwc

                c[STATUS_KEY_END] = self.ts()
                c[STATUS_KEY_END_MS] = utime.ticks_ms()
                c[STATUS_KEY_PULSES] = pulses
                c[STATUS_KEY_VOL_L] = vol_l
                c[STATUS_KEY_CE_MWH] = ce_mwh
                c[STATUS_KEY_FINAL_SOIL_MOISTURE_VWC] = soil_moisture_vwc

                duration_ms = int(utime.ticks_diff(c[STATUS_KEY_END_MS], c[STATUS_KEY_START_MS]))
                duration_s = float(duration_ms)/1000.0
                c[STATUS_KEY_DURATION] = duration_s


                if soil_moisture_vwc is None or soil_moisture_vwc is False or not isinstance(soil_moisture_vwc,(float, int)):
                    soil_moisture_vwc = 0.0

                d = IrrigationData(irrigationid = c[STATUS_KEY_ID],
                                ts_start=c[STATUS_KEY_START], ts_end=c[STATUS_KEY_END],
                                duration=duration_s,
                                pulses=pulses, vol_l=vol_l,
                                ce_mwh=ce_mwh,
                                vbatt=vbatt,
                                vpump=vpump,
                                ipump=ipump,
                                initial_sm_vwc=c[STATUS_KEY_INITIAL_SOIL_MOISTURE_VWC],
                                final_sm_vwc=soil_moisture_vwc)

                self.add_irrigation_cycle(d)

                #print (d.to_dict())

                IrrigationData.append_to_file(PINOUT.IRRIGATION_DATA_FN, l=[d])
                self._last_irrigation_cycle = d
                self._current_irrigation_cycle = None
        except Exception as ex:
            self._logger.exc(ex,"status.end_irrigation_cycle exception: {e}".format(e=str(ex)))



    #
    #
    # RAIN
    #
    #

    def rain_measures(self):
        """
        [
            {
                "id":0,
                "start": "",
                "end": "",
                "duration_h": 0,
                "pulses": "",
                "mmph": 0,
                "soil_moisture_vwc": 0
            }
        ]
        """
        return self._rain_measures

    def add_rain_measure(self, pulses, mmph):

        self.rain_mmph = mmph

        ts_end_str = self.ts(),
        ts_end = timetools.totimestamp(ts_end_str)

        if self._last_rain_measure is not None:
            rainid = int(self._last_rain_measure.rainid) + 1
            ts_start_str = self._last_rain_measure.ts_end
            ts_start = timetools.totimestamp(ts_start_str)
            duration_h = float(ts_end-ts_start) / 3600.0
        else:
            rainid = 0
            ts_start = ts_end-3600
            ts_start_str = timetools.tostr(ts_start)
            duration_h = 1

        soil_moisture_vwc=self.soil_moisture_vwc

        if soil_moisture_vwc is None or soil_moisture_vwc is False or not isinstance(soil_moisture_vwc,(float, int)):
            soil_moisture_vwc = 0.0

        aux_rain_data = RainData(rainid = rainid,
                        ts_start=ts_start_str, ts_end=ts_end_str,
                        pulses=pulses, mmph=mmph,
                        soil_moisture_vwc=soil_moisture_vwc)

        self._rain_measures.append(aux_rain_data)

        #print (aux_rain_data.to_dict())

        RainData.append_to_file(PINOUT.RAIN_DATA_FN, l=[aux_rain_data])
        self._last_rain_measure = aux_rain_data

        if len(self._rain_measures) < 100:
            self._rain_measures.append(aux_rain_data)

    def elapsed_since_last_rain_measure_h(self):
        ts_end_str = self.ts(),
        ts_end = timetools.totimestamp(ts_end_str)

        if self._last_rain_measure is not None:
            ts_start_str = self._last_rain_measure.ts_end
            ts_start = timetools.totimestamp(ts_start_str)
            if ts_start is None:
                self._logger.error("Failed to convert last rain end '{e}' ({a}) to timestamp -> {t}".format(
                    e=ts_start_str,t=str(ts_start), a=str(type(ts_start_str))))
            if ts_start is not None and ts_end is not None:
                try:
                    duration_h = float(ts_end-ts_start) / 3600.0
                except Exception as ex:
                    self._logger.exc(ex, "Failed to substract {e}-{s}".format(e=str(ts_end), s=(ts_start)))
            else:
                duration_h = None
        else:
            duration_h = None
        return duration_h

    def clear_rain_measures(self, mark_sent=False):
        if mark_sent:
            try:
                l = []
                for ir in self._rain_measures:
                    c = RainDataCommunication(ir.rainid)
                    l.append(c)
                RainDataCommunication.append_to_file(PINOUT.RAIN_COMMUNICATION_REGISTER_FN, l)
            except Exception as ex:
                self._logger.exc(ex,"status.clear_rain_measures exception: {e}".format(e=str(ex)))


        self._rain_measures.clear()


    #
    #
    # POWER
    #
    #

    def clear_power_measures(self):
        power_monitor.clear_power_measures()

    @property
    def power_measures(self):
        return power_monitor.power_measures()


    @property
    def last_power_measure(self):
        return self._last_power_measure

    def bus_voltage(self, name):
        v = None
        if (self._last_power_measure is not None) and (name in self._last_power_measure):
            bus_values = self._last_power_measure[name]
            if 'v' in bus_values:
                v = bus_values['v']
        return v

    def bus_current(self, name):
        i = None
        if (self._last_power_measure is not None) and (name in self._last_power_measure):
            bus_values = self._last_power_measure[name]
            if 'i' in bus_values:
                i = bus_values['i']
        return i

    @property
    def batt_v(self):
        return self.bus_voltage('batt')

    @property
    def pv_v(self):
        return self.bus_voltage('pv')

    @property
    def pump_v(self):
        return self.bus_voltage('pump')

    @property
    def pump_i(self):
        return self.bus_current('pump')

    @property
    def ps5v_v(self):
        return self.bus_voltage('5v')

    def add_power_measure(self, m):
        try:
            if m is not None:
                self._last_power_measure = m
                if 'pv' in m:
                    d = m['pv']
                    self._status_data.vpv = d['v']
                    self._status_data.ipv = d['i']
                if 'batt' in m:
                    d = m['batt']
                    self._status_data.vbatt = d['v']
                    self._status_data.ibatt = d['i']
                if 'pump' in m:
                    d = m['pump']
                    self._status_data.vpump = d['v']
                    self._status_data.ipump = d['i']
            else:
                #self._logger.info("add_power_measure: Discarded because the measure is None")
                pass
        except Exception as ex:
            self._logger.exc(ex,"add_power_measure error: {e}".format(e=str(ex)))

    #
    #
    # STATUS
    #
    #

    @property
    def status_bin(self):
        self._status_data.ts = self.ts() # Update the TS before packing
        self._status = {
            CFG.K_ID: self._static_config[CFG.K_ID],
            STATUS_KEY_TS: self.ts(),
            STATUS_KEY_STATUS: b64encode(self._status_data.to_bin()),
            STATUS_KEY_POWER: b64encode(power_monitor.to_bin()),
            STATUS_KEY_LAST_UPDATE_CHECK: self._last_update_check
        }

        return self._status

    @status_bin.setter
    def status_bin(self, value):
        try:
            s = value[STATUS_KEY_STATUS]
            s_decoded = b64decode(s)
            self._status_data.from_bin(s_decoded)
            if STATUS_KEY_LAST_UPDATE_CHECK in s:
                self._last_update_check = s[STATUS_KEY_LAST_UPDATE_CHECK]
            else:
                self._last_update_check = None
        except Exception as ex:
            self._logger.exc(ex,"status.setter exception: {e}".format(e=str(ex)))
            self._logger.debug("value = {v}".format(v = ujson.dumps(value)))

    @property
    def status(self):
        
        sw_ver = None
        fw_ver = None
        try:
            sw_ver = tools.get_version()
            fw_ver = tools.get_fw_version()
            
            sw_ver = "{v:<8}".format(v=sw_ver[:8])
            fw_ver = "{v:<44}".format(v=fw_ver[:44])
            
        except Exception as ex:
            print("Error: {e}".format(e=str(ex)))
            t = os.uname()
            fw_ver = t.version
            
        
        self._status_data.ts = self.ts() # Update the TS before packing
        self._status_data.sw_ver = sw_ver
        self._status_data.fw_ver = fw_ver
        
        self._status = {
            CFG.K_ID: self._static_config[CFG.K_ID],
            STATUS_KEY_TS: self.ts(),
            STATUS_KEY_STATUS: self._status_data.to_dict(),
            STATUS_KEY_POWER: power_monitor.to_dict(),
            STATUS_KEY_LAST_UPDATE_CHECK: self._last_update_check
        }

        return self._status

    @status.setter
    def status(self, value):
        try:
            s = value[STATUS_KEY_STATUS]
            self._status_data.from_dict(s)
            if STATUS_KEY_LAST_UPDATE_CHECK in s:
                self._last_update_check = s[STATUS_KEY_LAST_UPDATE_CHECK]
            else:
                self._last_update_check = None
        except Exception as ex:
            self._logger.exc(ex,"status.setter exception: {e}".format(e=str(ex)))
            self._logger.debug("value = {v}".format(v = ujson.dumps(value)))


    def ts(self):
        dt = self._rtc.datetime()
        # (year, month, mday, week_of_year, hour, minute, second, milisecond)
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        return ts_str

    def check_battery_and_pump_status(self):
        hasChanged = False
        if self._last_power_measure is not None:
            _batt_v = self.batt_v
            if _batt_v is None:
                _batt_v = 0


            (th_dead, th_low) = self.get_vbatt_th()

            current_alarm_batt_dead = self._status_data.alarm_batt_dead
            current_alarm_batt_low = self._status_data.alarm_batt_low

            if _batt_v <= th_dead:
                new_alarm_batt_dead = True
                new_alarm_batt_low = True
                event_extra_data = "Battery is DEAD, voltage {v} [V] is below the threshold {th} [V]".format(v=_batt_v, th=th_dead)
            else:
                if _batt_v <= th_low:
                    new_alarm_batt_dead = False
                    new_alarm_batt_low = True
                    event_extra_data = "Battery is LOW, voltage {v} [V] is below the threshold {th} [V]".format(v=_batt_v, th=th_low)
                else:
                    new_alarm_batt_dead = False
                    new_alarm_batt_low = False
                    event_extra_data = "Battery is NORMAL, voltage {v} [V] is over the threshold {th} [V]".format(v=_batt_v, th=th_low)

            is_battery_alarmed = new_alarm_batt_dead or new_alarm_batt_low
            hasChanged = (current_alarm_batt_dead!=new_alarm_batt_dead) or (current_alarm_batt_low!=new_alarm_batt_low)

            if hasChanged:
                self._status_data.alarm_batt_dead = new_alarm_batt_dead
                self._status_data.alarm_batt_low = new_alarm_batt_low
                self.add_event(PlanterEvents.Alarm, is_battery_alarmed, event_extra_data)


            _pv_v = self.pv_v
            if _pv_v is None:
                _pv_v = 0
            current_alarm_pv = self._status_data.alarm_pv
            if _pv_v < PINOUT.V_PV_MIN:
                if current_alarm_pv is False:
                    event_extra_data = "PV is ALARMED, voltage {v} [V] is below the threshold {th} [V]".format(v=_pv_v, th=PINOUT.V_PV_MIN)
                    self.add_event(PlanterEvents.Alarm, True, event_extra_data)
                self._status_data.alarm_pv = True                
            else:
                if current_alarm_pv is True:
                    event_extra_data = "PV is NORMAL, voltage {v} [V] is over the threshold {th} [V]".format(v=_pv_v, th=PINOUT.V_PV_MIN)
                    self.add_event(PlanterEvents.Alarm, False, event_extra_data)
                self._status_data.alarm_pv = False
            
            _pump_v = self.pump_v
            _pump_i = self.pump_i

            if _pump_v is None:
                _pump_v = 0
            if _pump_i is None:
                _pump_i = 0
            
            ts_now = utime.time()

            if self.pump_on is False:
                elapsed_s = ts_now - self._ts_last_pump_stop
                if elapsed_s > 15:
                    th_pump_v = 3
                    th_pump_i = 0.1
                    current_alarm_pump_a = self._status_data.alarm_pump_a
                    pump_error = (_pump_v > th_pump_v) or (_pump_i > th_pump_i)
                    if pump_error:
                        if current_alarm_pump_a is False:
                            event_extra_data = "PUMP is ALARMED, PUMP should be OFF but is ACTIVE because voltage is {v} [V] (th={th_v} [V]) and current is {i} [a] (th={th_i})".format(
                                v=_pump_v, th_v=th_pump_v, i=_pump_i, th_i=th_pump_i)
                            self.add_event(PlanterEvents.Alarm, True, event_extra_data)
                            self._logger.warning(event_extra_data)
                        self._status_data.alarm_pump_a = True
                    else:
                        if current_alarm_pump_a is True:
                            event_extra_data = "PUMP is NORMAL, PUMP should be OFF and is no longer ACTIVE because voltage is {v} [V] (th={th_v} [V]) and current is {i} [a] (th={th_i})".format(
                                v=_pump_v, th_v=th_pump_v, i=_pump_i, th_i=th_pump_i)
                            self.add_event(PlanterEvents.Alarm, False, event_extra_data)
                            self._logger.debug(event_extra_data)
                        self._status_data.alarm_pump_a = False
            else:
                elapsed_s = ts_now - self._ts_last_pump_start
                if elapsed_s > 15:
                    current_alarm_pump_v = self._status_data.alarm_pump_v
                    current_alarm_pump_i = self._status_data.alarm_pump_i
                    current_alarm_flowmeter_none = self._status_data.alarm_flowmeter_none
                    current_alarm_flowmeter_inf = self._status_data.alarm_flowmeter_inf

                    current_alarm_pump = current_alarm_pump_v or current_alarm_pump_i
                    current_alarm_flowmeter = current_alarm_flowmeter_none or current_alarm_flowmeter_inf

                    if _pump_v < (_batt_v-4):
                        self._status_data.alarm_pump_v = True
                    else:
                        self._status_data.alarm_pump_v = False
                    if _pump_i < PINOUT.A_PUMP_MIN:
                        self._status_data.alarm_pump_i = True
                    else:
                        self._status_data.alarm_pump_i = False

                    new_alarm_pump = self._status_data.alarm_pump_v or self._status_data.alarm_pump_i

                    if current_alarm_pump != new_alarm_pump:
                        if current_alarm_pump_v is False:
                            event_extra_data = "PUMP is ALARMED, PUMP is ON but voltage is {v_pump} [V] (batt is {v_batt} [V]) and current is {i_pump} (th is {th_i} [A])".format(
                                v_pump=_pump_v, v_batt=_batt_v, i_pump=_pump_i, th_i=PINOUT.A_PUMP_MIN)
                            self.add_event(PlanterEvents.Alarm, True, event_extra_data)
                            self._logger.warning(event_extra_data)
                        else:
                            event_extra_data = "PUMP is NORMAL, PUMP is ON and voltage is {v_pump} [V] (batt is {v_batt} [V]) and current is {i_pump} (th is {th_i} [A])".format(
                                v_pump=_pump_v, v_batt=_batt_v, i_pump=_pump_i, th_i=PINOUT.A_PUMP_MIN)
                            self.add_event(PlanterEvents.Alarm, False, event_extra_data)
                            self._logger.debug(event_extra_data)

                    pulse_count = self.pulse_count
                    if self.has_flow_meter:
                        if pulse_count < 2:
                            self._status_data.alarm_flowmeter_none = True
                        else:
                            self._status_data.alarm_flowmeter_none = False
                        if pulse_count > 5000:
                            self._status_data.alarm_flowmeter_inf = True
                        else:
                            self._status_data.alarm_flowmeter_inf = False

                    new_alarm_flowmeter = self._status_data.alarm_flowmeter_none or self._status_data.alarm_flowmeter_inf

                    if current_alarm_flowmeter != new_alarm_flowmeter:
                        if current_alarm_flowmeter is False:
                            event_extra_data = "FLOW METER is ALARMED, measured {p} pulses in {elapsed_s} [s]".format(
                                p=pulse_count, elapsed_s=elapsed_s)
                            self.add_event(PlanterEvents.Alarm, True, event_extra_data)
                            self._logger.warning(event_extra_data)
                        else:
                            event_extra_data = "FLOW METER is NORMAL, measured {p} pulses in {elapsed_s} [s]".format(
                                p=pulse_count, elapsed_s=elapsed_s)
                            self.add_event(PlanterEvents.Alarm, False, event_extra_data)
                            self._logger.debug(event_extra_data)

    def check_status(self):
        # If the power monitor is not available, then we cannot read voltages and currents of battery, pv and pump
        if self.has_ina3221_12v:
            self.check_battery_and_pump_status()

        self._status_data.alarm_wifi = NetworkMgr.wifi_error()
        self._status_data.alarm_gprs = NetworkMgr.ppp_error()


    def full_status(self):
        fs = {
            #"params": self.params,
            "status": self.status_bin, #self._status_data.to_dict(),
            "icycle": self._current_irrigation_cycle,
            "pump": {
                "ts_last_start": self._ts_last_pump_start,
                "ts_last_stop": self._ts_last_pump_stop
            },
            "post":
            {
                "status": self._ts_last_status_post
            },
            "params_ts": self._params_ts # Store when we read the parameters last time

        }
        return fs

    def set_full_status(self, fs):
        #ba = fs["status"]
        #self._status_data.from_ba(ba)
        #self._status_data.from_dict(fs["status"]        )
        self.status_bin = fs["status"]

        if "params_ts" in fs:
            self._params_ts = fs["params_ts"]
        else:
            # Estimate params_ts
            self._params_ts = PlanterStatus.estimate_params_ts(self._logger)

        self._current_irrigation_cycle = fs["icycle"]
        d_pump = fs["pump"]
        self._ts_last_pump_start = d_pump["ts_last_start"]
        self._ts_last_pump_stop = d_pump["ts_last_stop"]
        d_post = fs["post"]
        self._ts_last_status_post = d_post["status"]


    def store_status(self):
        # Store in RTC memory
        s = ""
        try:
            fs = self.full_status()
            s = ujson.dumps(fs)
            l = len(s)
            self._logger.debug("Store status in RCT RAM, {l} bytes ...".format(l=l))
            self._rtc.memory(s)  # Save in RTC RAM
        except Exception as ex:
            self._logger.exc(ex,"store_status error: {e}\nContents: {c}".format(e=ex,c=s))

    def retrieve_status(self):
        # Retrieve from RTC memory
        self._logger.debug("Retrieve params from RTC memory ...")
        fs = ujson.loads(self._rtc.memory())
        self.set_full_status(fs)


    #
    #
    # EVENTS
    #
    #

    def add_event(self, event_type, event_value, event_extra_data=""):
        self._events.append(
            {
                CFG.K_ID: self._static_config[CFG.K_ID],
                STATUS_KEY_TS: self.ts(),
                EVENT_KEY_TYPE: event_type,
                EVENT_KEY_VALUE: event_value,
                EVENT_KEY_EXTRADATA: tools.remove_ascii_colors(event_extra_data)
            }
        )

    def events(self):
        return self._events

    def clear_events(self):
        self._events.clear()

    #
    #
    # DISPLAY
    #
    #


    @property
    def display_page(self):
        return self._display_page

    @display_page.setter
    def display_page(self, value):
        self._display_page = value

    @property
    def display_mode(self):
        return self._display_mode

    @display_mode.setter
    def display_mode(self, value):
        self._display_mode = value

    def inc_display_page(self):
        self._display_page += 1
        if self._display_page > PlanterStatus.MAX_PAGE_NUMBER:
            self._display_page = PlanterStatus.PAGE_POWER_12V

    def _update_statvfs(self):
        try:
            ts_now = utime.time()
            elapsed_s = ts_now - self._ts_last_fs_check
            if (elapsed_s > 300) or (self._total_bytes is None) or (self._total_bytes==0):
                self._ts_last_fs_check = ts_now
                s = os.statvfs('/')
                new_total_bytes = s[0] * s[2]
                new_free_bytes = s[1] * s[3]
                has_changed = False
                if self._total_bytes != new_total_bytes:
                    self._total_bytes = new_total_bytes
                    has_changed = True
                if self._free_bytes != new_free_bytes:
                    self._free_bytes = new_free_bytes
                    has_changed = True
                self._used_bytes = self._total_bytes-self._free_bytes
                if has_changed:
                    self._logger.debug("FileSystem: Total {t}, free {f}, used {u}".format(t=self._total_bytes, f=self._free_bytes, u=self._used_bytes))

        except Exception as ex:
            self._total_bytes = 0
            self._free_bytes = 0
            self._used_bytes = 0

    def fs_screen(self):
        self._update_statvfs()
        # Prepare contents
        display_lines = [
            "FileSystem:",
            "total {t:>7}".format(t=self._total_bytes),
            "free {t:>7}".format(t=self._free_bytes),
            "used {t:>7}".format(t=self._used_bytes),
            "{ts}".format(ts=self.ts())
        ]
        return display_lines

    def connection_screen(self):
        return NetworkMgr.connection_screen()


    def soil_moisture_screen(self):
        lines = None
        try:
            lines = [
                "Soil Moisture Sensor",
                "RH   {rh:>5.1f} %".format(rh=self._status_data.soil_moisture_vwc),
                "Temp {t:>5.1f} oC".format(t=self._status_data.soil_temperature_c),
                "",
                "{ts}".format(ts=self.ts())
            ]
        except Exception as ex:
            pass
        return lines

    def pump_screen(self):
        lines = None
        try:
            e = self._pump_details[1]
            l = power_monitor.to_display("12v")
            lines = [
                "Pump {s}".format(s="ON" if self._pump_details[0] else "OFF"),
                "{e} [s]".format(e=e if e<99999 else "INF"),
                "{p:>4}p {v}ml".format(p=self._pump_details[2],v=int(self._pump_details[3])),
                "{p}".format(p=l[2] if l is not None else ""),
                "RH  {rh:>5.1f} %".format(rh=self._status_data.soil_moisture_vwc)
            ]
        except Exception as ex:
            pass
        return lines


    def get_screen(self, idx=None):
        if idx is None:
            ts_now_ticks_ms = utime.ticks_ms()
            elapsed_s = utime.ticks_diff(ts_now_ticks_ms, self._ts_last_button1_pressed_ticks_ms)/1000
            if elapsed_s > DISPLAY_TIMEOUT_SECONDS and (self._display_mode == 0):
                # Power off display
                self.display_page = PlanterStatus.PAGE_OFF
            idx = self.display_page
        result = ["","","","","", False]
        if idx == PlanterStatus.PAGE_OFF:
            # OFF
            result = ["","","","","", False]
        elif idx == PlanterStatus.PAGE_WIFI:
            # WIFI
            result = [self.connection_screen(), True]
        elif idx == PlanterStatus.PAGE_FS:
            # Filesystem
            result = [self.fs_screen(), True]
        elif idx == PlanterStatus.PAGE_POWER_12V:
            # POWER
            l = power_monitor.to_display("12v")
            if l is not None:
                f_short = "{flow_count:>5} |{flow_lpm:>5.2f} L/m".format(
                    flow_count = self._pps or 0, flow_lpm=self.flow_lpm or 0)
                l[4] = f_short
                result = ([l[0],l[1],l[2],l[3],l[4]], True)
        elif idx == PlanterStatus.PAGE_POWER_5V:
            # POWER
            if power_monitor.has_pm("5v"):
                l = power_monitor.to_display("5v")
                if l is not None:
                    f_short = "{flow_count:>5} |{flow_lpm:>5.2f} L/m".format(
                    flow_count = self._pps or 0, flow_lpm=self.flow_lpm or 0)
                    l[4] = f_short
                    result = ([l[0],l[1],l[2],l[3],l[4]], True)
            else:
                result = (["5V POWER","MONITOR","NOT","INSTALLED",""], True)
        elif idx == PlanterStatus.PAGE_SOIL_MOISTURE:
            # Soil moisture
            result = [self.soil_moisture_screen(), True]
        elif idx == PlanterStatus.PAGE_PUMP:
            # Soil moisture
            result = [self.pump_screen(), True]
        return result


    #
    #
    # URL
    #
    #

    @property
    def config_url(self):
        return self._config_url

    @property
    def params_url(self):
        return self._params_url

    @property
    def events_url(self):
        return self._events_url

    @property
    def status_url(self):
        return self._status_url

    @property
    def traces_url(self):
        return self._traces_url

    @property
    def irrigation_url(self):
        return self._irrigation_url

    @property
    def power_url(self):
        return self._power_url

    @property
    def rain_url(self):
        return self._rain_url

    @property
    def messages_url(self):
        return self._messages_url

    @property
    def server_hostname(self):
        self.update_url()
        return self._server
    
    @property
    def server_port(self):
        self.update_url()
        return self._port
    
    def update_url(self):

        # Use internal agent address if connected by WiFi
        # Use external agent address if connected by GPRS
        wifi_connected = NetworkMgr.wifi_connected() 
        bInternal = wifi_connected

        try:
            if bInternal:
                a = self._static_config[CFG.K_AGENT_INT]
            else:
                a = self._static_config[CFG.K_AGENT_EXT]
        except:
            a = self._static_config[CFG.K_AGENT]

        if CFG.K_PROTOCOL in self._static_config:
            self._protocol = self._static_config[CFG.K_PROTOCOL]
        else:
            self._protocol = "https"

        self._use_internal = bInternal
        self._server = None
        self._port = None
        try:
            if a is not None and len(a):
                server_parts = a.split(':')
                if server_parts:
                    if len(server_parts)>0:
                        self._server = server_parts[0]
                    if len(server_parts)>1:
                        try:
                            self._port = int(server_parts[1])
                        except Exception as ex:
                            self._logger.exc(ex,"update_url error: {e}".format(e=str(ex)))
                else:
                    self._logger.error("Agent hostname:port '{a}' cannot be parsed".format(a=a))
            else:
                self._logger.error("Agent hostname:port is null or empty")
        except Exception as ex:
            self._logger.exc(ex,"update_url error: {e}".format(e=str(ex)))
        
        j = self._static_config[CFG.K_ID]
        url_base = "{protocol}://{agent}".format(protocol = self._protocol, agent=a)
        
        self._config_url = "{url_base}/config/{id}".format(url_base=url_base, id=j)
        self._params_url = "{url_base}/params/{id}".format(url_base=url_base, id=j)
        self._status_url = "{url_base}/status/{id}".format(url_base=url_base, id=j)
        self._traces_url = "{url_base}/traces/{id}".format(url_base=url_base, id=j)
        self._events_url = "{url_base}/events/{id}".format(url_base=url_base, id=j)
        self._irrigation_url = "{url_base}/irrigation/{id}".format(url_base=url_base, id=j)
        self._power_url = "{url_base}/power/{id}".format(url_base=url_base, id=j)
        self._rain_url = "{url_base}/rain/{id}".format(url_base=url_base, id=j)
        self._messages_url = "{url_base}/messages/{id}".format(url_base=url_base, id=j)



    #
    #
    # CONTROL MODE
    #
    #

    @property
    def control_mode(self):
        r = None
        try:
            if CFG.K_MODE in self.params:
                r = int(self.params[CFG.K_MODE])
            else:
                r = None
        except:
            pass
        return r


    def is_periodic_control_mode_active(self):
        cm = self.control_mode
        if cm is not None:
            return (self.control_mode & CFG.CONTROL_MODE_FLAG_PERIODIC) == CFG.CONTROL_MODE_FLAG_PERIODIC
        else:
            return None

    def is_calendar_control_mode_active(self):
        cm = self.control_mode
        if cm is not None:
            return (self.control_mode & CFG.CONTROL_MODE_FLAG_CALENDAR) == CFG.CONTROL_MODE_FLAG_CALENDAR
        else:
            return None

    def is_soil_moisture_control_mode_active(self):
        cm = self.control_mode
        if cm is not None:
            return (self.control_mode & CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE) == CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE
        else:
            return None

    def is_forced_control_mode_active(self):
        cm = self.control_mode
        if cm is not None:
            return (self.control_mode & CFG.CONTROL_MODE_FLAG_FORCED) == CFG.CONTROL_MODE_FLAG_FORCED
        else:
            return None

    def is_disabled_control_mode_active(self):
        cm = self.control_mode
        if cm is not None:
            return (self.control_mode & CFG.CONTROL_MODE_FLAG_DISABLED) == CFG.CONTROL_MODE_FLAG_DISABLED
        else:
            return None

    def get_control_mode_tuple(self):
        cm = self.control_mode
        if cm is not None:
            cm_p = (cm & CFG.CONTROL_MODE_FLAG_PERIODIC) == CFG.CONTROL_MODE_FLAG_PERIODIC
            cm_c = (cm & CFG.CONTROL_MODE_FLAG_CALENDAR) == CFG.CONTROL_MODE_FLAG_CALENDAR
            cm_sm = (cm & CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE) == CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE
            cm_f = (cm & CFG.CONTROL_MODE_FLAG_FORCED) == CFG.CONTROL_MODE_FLAG_FORCED
            cm_d = (cm & CFG.CONTROL_MODE_FLAG_DISABLED) == CFG.CONTROL_MODE_FLAG_DISABLED

            if cm_sm and  self.has_sm_sensor is False:
                # If there is no soil moisture sensor configured, then change from sm mode to periodic mode
                cm_sm = False
                cm_p = True

            return (cm_p, cm_c, cm_sm, cm_f, cm_d)
        else:
            return (None, None, None, None)


    @property
    def periodic_mode_pump_period_s(self):
        r = 3600*24
        try:
            if CFG.K_PERIODIC in self.params:
                r = int(self.params[CFG.K_PERIODIC][CFG.K_PUMP_PERIOD_S])
        except:
            pass
        return r

    @property
    def periodic_mode_pump_max_duration_s(self):
        r = 50
        try:
            if CFG.K_PERIODIC in self.params:
                r = int(self.params[CFG.K_PERIODIC][CFG.K_MAX_DURATION_S])
        except:
            pass
        return r

    @property
    def periodic_mode_pump_max_volume_ml(self):
        r = 4000
        try:
            if CFG.K_PERIODIC in self.params:
                r = float(self.params[CFG.K_PERIODIC][CFG.K_MAX_VOL_ML])
        except:
            pass
        return r

    @property
    def rain_th_mmph(self):
        r = 150
        try:
            if CFG.K_RAIN_TH_MMPH in self.params:
                r = float(self.params[CFG.K_RAIN_TH_MMPH])
        except:
            pass
        return r

    @property
    def rain_prob_th(self):
        r = 0
        try:
            r = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_RAIN_PROBABILITY_TH])
        except:
            pass
        return r

    @property
    def rain_prob(self):
        r = 0
        try:
            r = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_RAIN_PROBABILITY])
        except:
            pass
        return r

    @property
    def iprot_time(self):
        r = 15
        try:
            r = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_IRR_PROTECTION_TIME])
        except:
            pass
        return r

    @property
    def iprot_minpulses(self):
        r = 20
        try:
            r = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_IRR_PROTECTION_MINPULSES])
        except:
            pass
        return r


    @property
    def flow_en_hysteresis(self):
        r = True
        try:
            r = self.params[CFG.K_ADVANCED][CFG.K_ADV_FLOW_ENABLE_HYSTERESIS] is True
        except:
            pass
        return r

    def get_vbatt_th(self):
        # Default value
        th_dead = 9.5
        th_low = 10.8

        # Try to get the thresholds from the parameters.
        # If there has been an error in getting the parameters, the following may fail
        try:
            th_dead = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_V_BATT_DEAD])
            th_low = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_V_BATT_LOW])
        except:
            pass
        return (th_dead, th_low)


    def get_vbatt_min_for_pump(self):
        vbatt_min_for_pump = 11
        try:
            vbatt_min_for_pump = float(self.params[CFG.K_ADVANCED][CFG.K_ADV_V_BATT_MIN_FOR_PUMP])
        except:
            pass
        return vbatt_min_for_pump

    def get_sm_params(self):
        sm_low_th = 23.0
        sm_pump_min_period_s = 7200
        sm_mode_max_sleep_s = 3600*24
        try:
            sm_low_th = self.soil_moisture_th
            sm_pump_min_period_s = int(self.params[CFG.K_ADVANCED][CFG.K_ADV_SOIL_MOISTURE_BASED_PUMP_MIN_PERIOD_S])
            sm_mode_max_sleep_s = int(self.params[CFG.K_ADVANCED][CFG.K_ADV_SOIL_MOISTURE_CONTROL_MAX_SLEEP_S])
        except:
            pass
        return (sm_low_th, sm_pump_min_period_s, sm_mode_max_sleep_s)

    def get_door_open_max_sleep_s(self):
        door_open_max_sleep_s = 1800
        try:
            door_open_max_sleep_s = int(self.params[CFG.K_ADVANCED][CFG.K_ADV_DOOR_OPEN_MAX_SLEEP_S])
        except:
            pass
        return door_open_max_sleep_s

    #
    #
    # PARAMS
    #
    #


    @property
    def params(self):
        #return self._params
        return CFG.params()

    @params.setter
    def params(self, value):
        
        params_valid = True
        if value is None or len(value)==0:
            params_valid = False
        if CFG.K_ADVANCED not in value:
            params_valid = False
        
        if params_valid is False:
            self._logger.error("Invalid params '{p}' -> DISCARD".format(p=str(value)))
            return


        self._logger.debug("Set params")
        self._params_ts = PlanterStatus.estimate_params_ts(self._logger)

        try:
            # Fix configuration if there are missing elements
            if CFG.K_MODE not in value:
                #self._params[K_MODE] = CONTROL_MODE_FLAG_PERIODIC | CONTROL_MODE_FLAG_SOIL_MOISTURE
                value[CFG.K_MODE] = CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE
            
            m = int(value[CFG.K_MODE])
            value[CFG.K_MODE] = m  # Ensure that we store the mode as integer
            
            if m & CFG.CONTROL_MODE_FLAG_PERIODIC:
                if CFG.K_PERIODIC not in value:
                    value[CFG.K_PERIODIC] ={
                        CFG.K_PUMP_PERIOD_S: const(3600*24/2),
                        CFG.K_MAX_VOL_ML: 4000.0,
                        CFG.K_MAX_DURATION_S: 50
                    }

        except Exception as ex:
            self._logger.exc(ex,"params.setter exception: {e}".format(e=str(ex)))


        # ALLOW ONLY ONE CONTROL MODE ACTIVE
        v = int(value[CFG.K_MODE])

        if v & CFG.CONTROL_MODE_FLAG_PERIODIC:
            self._logger.info("Control mode: {c}PERIODIC{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
            v = CFG.CONTROL_MODE_FLAG_PERIODIC
        elif v & CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE:
            if self.has_sm_sensor is False:
                v = CFG.CONTROL_MODE_FLAG_PERIODIC
                self._logger.warning("Control mode changed from SOIL MOISTURE to {c}PERIODIC{n} because there is no soil moisture sensor configured".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
            else:
                v = CFG.CONTROL_MODE_FLAG_SOIL_MOISTURE
                self._logger.info("Control mode: {c}SOIL MOISTURE{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
        elif v & CFG.CONTROL_MODE_FLAG_CALENDAR:
            v = CFG.CONTROL_MODE_FLAG_CALENDAR
            self._logger.info("Control mode: {c}CALENDAR{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
        elif v & CFG.CONTROL_MODE_FLAG_FORCED:
            v = CFG.CONTROL_MODE_FLAG_FORCED
            self._logger.info("Control mode: {c}FORCED{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
        elif v & CFG.CONTROL_MODE_FLAG_DISABLED:
            v = CFG.CONTROL_MODE_FLAG_DISABLED
            self._logger.info("Control mode: {c}DISABLED{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL))
        value[CFG.K_MODE] = v

        if CFG.K_ADVANCED not in value:
            value[CFG.K_ADVANCED] = {}
        advanced = value[CFG.K_ADVANCED]
        if CFG.K_ADV_WORK_FLOW_LPH not in advanced:
            advanced[CFG.K_ADV_WORK_FLOW_LPH] = PINOUT.WORK_FLOW_LPH
        if CFG.K_ADV_WORK_FLOW_PULSE_FREQ_HZ not in advanced:
            advanced[CFG.K_ADV_WORK_FLOW_PULSE_FREQ_HZ] = PINOUT.WORK_FLOW_PULSE_FREQ_HZ

        CFG.set_params(value)

        self.update_calendar()

    # Calculate Pulses-per-litre in the nominal flow workpoint
    def work_flow_ppl(self):
        p = self.params
        flow_lph = float(p[CFG.K_ADVANCED][CFG.K_ADV_WORK_FLOW_LPH])
        flow_pulse_freq_hz = float(p[CFG.K_ADVANCED][CFG.K_ADV_WORK_FLOW_PULSE_FREQ_HZ])
        flow_ppl = float(flow_pulse_freq_hz * 3600.0 / flow_lph)
        return flow_ppl


    def get_float_param(self, item, key, default_value=None):
        r = default_value
        if key in item:
            v = item[key]
            if v is not None and str(v) is not 'None':
                r =  float(v)
        return r

    def get_int_param(self, item, key, default_value=None):
        r = default_value
        if key in item:
            v = item[key]
            if v is not None and str(v) is not 'None':
                r =  int(v)
        return r

    def update_calendar(self):
        self._logger.debug("Update calendar")
        p = CFG.params()
        if CFG.K_CALENDAR in p:
            regex = ure.compile("^(\d?\d):(\d\d)$")
            c = p[CFG.K_CALENDAR]
            new_calendar = {}
            for item in c:
                c_start = item[CFG.K_START]
                m = regex.match(c_start)
                if m:
                    hh = int(m.group(1))
                    if hh < 0:
                        hh = hh + 24
                    mm = int(m.group(2))
                    s = hh*3600+mm*60
                    # (second, max duration, max vol, min moisture, start string)
                    
                    aux_max_duration = self.get_int_param(item, CFG.K_MAX_DURATION_S, None)
                    aux_max_vol_ml = self.get_float_param(item, CFG.K_MAX_VOL_ML, None)
                    aux_moisture_low_th = self.get_float_param(item, CFG.K_MOISTURE_LOW_TH, None)
                    
                    new_calendar[s] = (s, aux_max_duration, aux_max_vol_ml, aux_moisture_low_th, c_start)
            self._calendar = new_calendar
            gc.collect()
        else:
            self._calendar.clear()

    @property
    def calendar(self):
        return self._calendar

    @property
    def params_ts(self):
        return self._params_ts


    def params_age_s(self):
        ts_now = utime.time()
        elapsed_s = ts_now - self.params_ts
        return elapsed_s


    def get_params_period_s(self):
        r = 24*3600
        try:
            r = int(self.params[CFG.K_ADVANCED][CFG.K_ADV_SERVER_GET_PARAMS_PERIOD_S])
        except:
            pass
        return r

    def has_to_get_params(self):
        l = self.get_params_period_s()
        r = (self.params_age_s() > l)
        return r

    def pending_s_to_get_params(self):
        l = self.get_params_period_s()
        s = l-self.params_age_s()
        if s < 0:
            # params age is for sure not correct
            # so we cannot use it
            # just return the standard params_period_s
            # because we are reading the parameters on every connection
            s = l
        return s

    @staticmethod
    def estimate_params_ts(logger):
        try:
            # Estimate the last time that params were read
            # This will be updated with the information read from the RTC memory
            svr_get_params_period_s = int(CFG.svr_get_params_period_s())
            result = utime.time() - (svr_get_params_period_s + 120)
        except Exception as ex:
            logger.exc(ex,"status.init exception: {e}".format(e=str(ex)))
            # Failed to estimate, just set zero
            result = 0
        return result

    #
    #
    # INIT
    #
    #

    def __init__(self, rtc):

        self._logger = logging.getLogger("PlanterStatus")
        self._logger.setLevel(logging.DEBUG)

        self._soil_moisture_status = PlanterEvents.VALUE_NORMAL
        self._soil_moisture_data_available = False
        self._soil_moisture_read_trial = 0
        self._last_update_check = 0
        self._current_irrigation_cycle = None
        self._events = []
        self._total_bytes = 0
        self._free_bytes = 0
        self._used_bytes = 0
        self._rtc = machine.RTC()
        self._display_page = 0

        self._pulse_count = 0
        self._pps = 0

        self._button1 = True
        self._ts_last_status_post = 0
        self.has_ina3221_12v = False
        self.has_ina3221_5v = False
        self.has_ina226 = False
        self.has_display = False
        self.has_accelerometer = False
        self.accelerometer_model=[]
        self.has_mcp = False
        self._ts_last_level_change = None
        self._ts_last_power_measure_added = 0
        self._display_mode = 0
        ts_now = utime.time()
        ticks_ms_now = utime.ticks_ms()

        self._ts_last_button1_pressed_ticks_ms = ticks_ms_now-(PINOUT.MIN_TIME_FROM_BUTTON_PRESS_TO_SLEEP_S*1000)
        #self._ts_last_button1_pressed = ts_now
        self._ts_last_fs_check = ts_now

        self._ts_last_pump_start = -30000
        self._ts_last_pump_stop = -30000

        self._rtc=rtc
        self._wake_reason = machine.wake_reason()

        self._static_config = CFG.config()

        self._params_ts = PlanterStatus.estimate_params_ts(self._logger)

        self.update_calendar()
        logging.set_id(CFG.planter_id())

        try:
            self.has_flow_meter = CFG.has_flow_meter()
        except:
            self.has_flow_meter = False
        try:
            self.has_rain_sensor = CFG.has_rain_sensor()
        except:
            self.has_rain_sensor = False

        try:
            self.has_sm_sensor = CFG.has_sm_sensor()
        except:
            self.has_sm_sensor = False

        self._status_data = PlanterStatusData()
        rtc_memory_len = len(self._rtc.memory())

        if rtc_memory_len > 0:
            self.retrieve_status()

        self._irrigation_cycles = []
        self._last_power_measure = None
        self._status = {}
        self._last_di_values = ()
        
        self.downlink_messages = []
        
        # Ensure that data files exist
        tools.ensure_data_files()

        # Load irrigation data
        (last_irrigation_cycle, last_communicated_irrigation, li_not_communicated) = IrrigationData.load_not_communicated(PINOUT.IRRIGATION_DATA_FN, PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN)
        self._last_irrigation_cycle = last_irrigation_cycle
        self._last_communicated_irrigation = last_communicated_irrigation
        self._irrigation_cycles = li_not_communicated

        # Load rain data
        (last_rain_measure, last_communicated_rain, li_not_communicated) = RainData.load_not_communicated(PINOUT.RAIN_DATA_FN, PINOUT.RAIN_COMMUNICATION_REGISTER_FN)
        self._last_rain_measure = last_rain_measure
        self._last_communicated_rain = last_communicated_rain
        self._rain_measures = li_not_communicated

        if self._last_rain_measure is not None:
            self.rain_mmph = self._last_rain_measure.mmph

        self._protocol = None
        self._server = None
        self._port = None
        self.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP = PINOUT.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP   # Default value
           
        self.update_url()

        self._logger.debug("Config: {c}".format(c=self.static_config))
        self._logger.debug("Params: {p}".format(p=self.params))


        self._calendar = {}

        wake_str = "Wake reason {r} ({r_str}) time {t}".format(
            r=self._wake_reason, r_str = MACHINE_WAKE_UP_REASONS[self._wake_reason], t=ts_now)
        self._logger.info(wake_str)

        self.add_event(PlanterEvents.Wake, PlanterEvents.STATUS_ON, wake_str)

        # Load irrigation cycles
        

