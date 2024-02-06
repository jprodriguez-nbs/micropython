

import gc
import micropython
import machine
import tools
t="UMDC Status"
print(t)
tools.free(True)



import logging
import esp32
import os
import utime
import ujson
import sys
import ure

from micropython import const


import umdc_pinout as PINOUT
if PINOUT.IMPORT_FROM_APP:
    import frozen.umdc_config as CFG
    from frozen.networkmgr import NetworkMgr
else:
    import umdc_config as CFG
    from networkmgr import NetworkMgr

import colors
import tools


import timetools as timetools


try:
    import ubinascii
    from ubinascii import a2b_base64 as b64decode
    from ubinascii import b2a_base64 as b64encode
except:
    import base64
    from base64 import b64decode as b64decode
    from base64 import b64encode as b64encode

from constants import *
from nsUmdcStatusData import UmdcStatusData


print("{t}.UmdcStatus class".format(t=t))

class UmdcStatus():
       

    @property
    def battery(self):
        return 3984

    @property
    def low_bat(self):
        return False

    @property
    def data(self):
        return self._status_data

    def update_alarm(self, alarm_bit, value):
        self._status_data.update_alarm(alarm_bit, value)


    @property
    def temp(self):
        tf = 0
        if False:
            n = 10
            for i in range(n):
                tf = tf + esp32.raw_temperature()
            tf = tf / n
        else:
            tf = esp32.raw_temperature()
            
        tc = float(int(((tf-32.0)/1.8)*10))/10
        print("T = {0:4d} deg F or {1:5.1f}  deg C".format(tf,tc))
        return tc


    @property
    def ac220(self):
        return self._status_data.ac220

    @ac220.setter
    def ac220(self, value):
        if self._status_data.ac220 != value:
            self._status_data.ac220 = value
            if value:
                self.add_event(UmdcEvents.AC220, UmdcEvents.STATUS_ON,"ON")
                self.update_alarm(UmdcStatusData.ALARM_BIT_AC220, False)
            else:
                self.add_event(UmdcEvents.AC220, UmdcEvents.STATUS_OFF, "OFF")
                self.update_alarm(UmdcStatusData.ALARM_BIT_AC220, True)

    @property
    def mcb(self):
        return self._status_data.mcb

    @property
    def di1(self):
        return self._status_data.di1

    @property
    def di2(self):
        return self._status_data.di2


    @property
    def ai1(self):
        return self._status_data.ai1

    @property
    def ai2(self):
        return self._status_data.ai2

    @mcb.setter
    def mcb(self, value):
        if self._status_data.mcb != value:
            self._status_data.mcb = value
            if value:
                self.add_event(UmdcEvents.MCB, UmdcEvents.STATUS_ON,"ON")
                self.update_alarm(UmdcStatusData.ALARM_BIT_MCB, False)
            else:
                self.add_event(UmdcEvents.MCB, UmdcEvents.STATUS_OFF, "OFF")
                self.update_alarm(UmdcStatusData.ALARM_BIT_MCB, True)



    @property
    def ts_last_status_post(self):
        return self._ts_last_status_post

    @ts_last_status_post.setter
    def ts_last_status_post(self, value):
        self._ts_last_status_post = value





    def set_di(self, di_values, connection_str):
        hasChanged = False
        
        (self.ac220, self._status_data.di1, self._status_data.di2, self._status_data.ai1, self._status_data.ai2) = di_values

        if di_values != self._last_di_values:
            self._last_di_values = di_values
            f_str = "{c}, Power {power}, DI1 {di1}, DI2 {di2}, AI1 {ai1}, AI2 {ai2}".format(
                c = connection_str,
                power = '220Vac' if self.ac220 else 'batt',
                di1 = self._status_data.di1,
                di2 = self._status_data.di2,
                ai1 = self._status_data.ai1,
                ai2 = self._status_data.ai2
                )
            self._logger.info(f_str)
            hasChanged = True

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
    # STATUS
    #
    #

    @property
    def status_bin(self):
        self._status_data.ts = self.ts() # Update the TS before packing
        self._status = {
            CFG.K_ID: self._static_config[CFG.K_ID],
            KEY_TS: self.ts(),
            KEY_STATUS: b64encode(self._status_data.to_bin()),
            KEY_LAST_UPDATE_CHECK: self._last_update_check
        }

        return self._status

    @status_bin.setter
    def status_bin(self, value):
        try:
            s = value[KEY_STATUS]
            s_decoded = b64decode(s)
            self._status_data.from_bin(s_decoded)
            if KEY_LAST_UPDATE_CHECK in s:
                self._last_update_check = s[KEY_LAST_UPDATE_CHECK]
            else:
                self._last_update_check = None
        except Exception as ex:
            self._logger.exc(ex,"status.setter exception: {e}".format(e=str(ex)))
            self._logger.debug("value = {v}".format(v = ujson.dumps(value)))

    @property
    def status(self):
        self._status_data.ts = self.ts() # Update the TS before packing
        self._status = {
            CFG.K_ID: self._static_config[CFG.K_ID],
            KEY_TS: self.ts(),
            KEY_STATUS: self._status_data.to_dict(),
            KEY_LAST_UPDATE_CHECK: self._last_update_check
        }

        return self._status

    @status.setter
    def status(self, value):
        try:
            s = value[KEY_STATUS]
            self._status_data.from_dict(s)
            if KEY_LAST_UPDATE_CHECK in s:
                self._last_update_check = s[KEY_LAST_UPDATE_CHECK]
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


    def check_battery(self):
        hasChanged = False
        if self._last_power_measure is not None:
            _batt_v = self.batt_v
            if _batt_v is None:
                _batt_v = 0


            (th_dead, th_low) = self.get_vbatt_th()

            current_alarm_batt = self._status_data.alarm_batt

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
            hasChanged = (current_alarm_batt!=is_battery_alarmed) 

            if hasChanged:
                self._status_data.alarm_batt = is_battery_alarmed
                self.add_event(UmdcEvents.Alarm, is_battery_alarmed, event_extra_data)


    def check_status(self):
        self.check_battery()

        self._status_data.alarm_wifi = NetworkMgr.wifi_error()
        self._status_data.alarm_gprs = NetworkMgr.ppp_error()


    def full_status(self):
        fs = {
            #"params": self.params,
            "status": self.status_bin, #self._status_data.to_dict(),

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
            self._params_ts = UmdcStatus.estimate_params_ts(self._logger)

        d_post = fs["post"]
        self._ts_last_status_post = d_post["status"]


    def store_status(self):
        # Store in RTC memory
        s = ""
        try:
            fs = self.full_status()
            s = ujson.dumps(fs)
            del fs
            l = len(s)
            self._logger.debug("Store status in RCT RAM, {l} bytes ...".format(l=l))
            self._rtc.memory(s)  # Save in RTC RAM
            del s
        except Exception as ex:
            self._logger.exc(ex,"store_status error: {e}\nContents: {c}".format(e=ex,c=s))

    def retrieve_status(self):
        # Retrieve from RTC memory
        self._logger.debug("Retrieve params from RTC memory ...")
        m = self._rtc.memory()
        fs = ujson.loads(m)
        del m
        self.set_full_status(fs)


    #
    #
    # EVENTS
    #
    #

    def add_event(self, event_type, event_value, event_extra_data=""):
        # Control buffer size
        max_events = 20
        n = len(self._events)
        if n > max_events:
            i = n - max_events
            # Drop oldest events to keep the array limited
            self._events = self._events[i:]
            
        # Add event
        self._events.append(
            {
                CFG.K_ID: self._static_config[CFG.K_ID],
                KEY_TS: self.ts(),
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
    # CONTROL MODE
    #
    #


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



    #
    #
    # PARAMS
    #
    #


    @property
    def params(self):
        return CFG.params()

    @property
    def mb_params(self):
        return CFG.mb_params()

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
        self._params_ts = UmdcStatus.estimate_params_ts(self._logger)


        if CFG.K_ADVANCED not in value:
            value[CFG.K_ADVANCED] = {}
        advanced = value[CFG.K_ADVANCED]

        CFG.set_params(value)

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
            #svr_get_params_period_s = int(CFG.svr_get_params_period_s())
            svr_get_params_period_s = 7200
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

        self._logger = logging.getLogger("UmdcStatus")
        self._logger.setLevel(logging.DEBUG)

        self._last_update_check = 0
        self._events = []
        self._total_bytes = 0
        self._free_bytes = gc.mem_free()
        self._used_bytes = gc.mem_alloc()
        self._rtc = machine.RTC()

        self._ts_last_status_post = 0
        ts_now = utime.time()
        ticks_ms_now = utime.ticks_ms()

        self._ts_last_fs_check = ts_now

        self._rtc=rtc
        self._wake_reason = machine.wake_reason()

        tools.free()
        print("{t}.config".format(t=t))
        self._static_config = CFG.config()
        if K_ID not in self._static_config:
            CFG.init()

        self._params_ts = UmdcStatus.estimate_params_ts(self._logger)

        logging.set_id(CFG.umdc_id())


        tools.free()
        print("{t}.UmdcStatusData".format(t=t))
        self._status_data = UmdcStatusData()
        rtc_memory_len = len(self._rtc.memory())

        tools.free()
        print("{t}.retrieve_status".format(t=t))
        if rtc_memory_len > 0:
            self.retrieve_status()

        self._last_power_measure = None
        self._status = {}
        self._last_di_values = ()
        
        
        tools.free()
        print("{t}.ensure_data_files".format(t=t))
        # Ensure that data files exist
        tools.ensure_data_files()

        self._protocol = None
        self._server = None
        self._port = None

        tools.free()
        print("{t}.dump".format(t=t))
        self._logger.debug("Config: {c}".format(c=self.static_config))
        self._logger.debug("Params: {p}".format(p=self.params))

        #
        # MB Operation
        #

        # Communication with modbus slaves
        # 0 = all ok, 1 = some fail, 2 = all fail
        self.mb_slave_fail = 0
        # Key = slave_id
        # Value = True if communicating, else False
        self.mb_slave_communication_status = {}
        self.mb_nb_slaves = 0
        
        self.mb_ts_last_acquisition_time = None
        self.mb_ts_report_time = None
        
        
        #
        # MQTT connection statistics
        #
        self.socket_time_alive = None
        self.socket_time_down = None
        self.socket_ts_last_up = 0
        self.socket_ts_last_down = 0

        # Reset statistics
        self.reset_count = 0

        wake_str = "Wake reason {r} ({r_str}) time {t}".format(
            r=self._wake_reason, r_str = MACHINE_WAKE_UP_REASONS[self._wake_reason], t=ts_now)
        self._logger.info(wake_str)

        tools.free()
        print("{t}.add_event Wake".format(t=t))
        self.add_event(UmdcEvents.Wake, UmdcEvents.STATUS_ON, wake_str)
        print("{t} end of class init".format(t=t))