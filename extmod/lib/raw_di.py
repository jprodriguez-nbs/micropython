
print ("Raw DI: Load libraries")
import gc, sys
import machine
from machine import Pin
from machine import wake_reason
import logging
import ujson
import utime

import hwversion
import umdc_pinout as PINOUT

def raw_di(check_updates, recheck_water_sensor=0):

    _rtc = machine.RTC()
    # Check if wakeup is because of interrupt of door or accelerometer
    _log = logging.getLogger("di")
    _log.setLevel(logging.DEBUG)


    _rtc = machine.RTC()
    _fs = None
    _needs_to_check_update = True

    try:


        _wake_reason = machine.wake_reason()
        if _wake_reason == 0x5 or True:

            _elapsed_s = 12*3600
            if check_updates:
                _rtc_memory_len = len(_rtc.memory())
                _ts_now = utime.time()
                if _rtc_memory_len > 0:
                    _log.debug("Retrieve params from RTC memory ...")
                    _fs = ujson.loads(_rtc.memory())
                    if "status" in _fs:
                        if "last_update_check" in _fs["status"]:
                            last_update_check = _fs["status"]["last_update_check"]
                            if last_update_check is not None:
                                _elapsed_s = _ts_now - last_update_check
                            if _elapsed_s < 12*3600:
                                _needs_to_check_update = False

                if (_wake_reason == 0x5) or (_wake_reason == 0x2):
                    pass
            else:
  
            _log.info("Wake={w}, elapsed since last OTA update: {e} [s], needs_to_check version is {n}".format(
                w=_wake_reason, 
                e=_elapsed_s, n = _needs_to_check_update))

            

    except Exception as ex:
        _log.exc(ex, "Failed to check wakeup reason and dia status")

    return (_needs_to_check_update, _fs, _rtc)