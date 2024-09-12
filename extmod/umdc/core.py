
import gc
import micropython
import machine
import tools
print("UMDC Core")
tools.free(True)




import time
import os
import io
import sys

import logging
gc.collect()

import json
import esp32
from machine import Pin, sleep, time_pulse_us, disable_irq, enable_irq, Timer, WDT
from constants import *
gc.collect()

import  asyncio
gc.collect()

import utime
import ubinascii
import ujson

import hwversion
gc.collect()

import umdc_pinout as PINOUT
if PINOUT.IMPORT_FROM_APP:
    from frozen.networkmgr import NetworkMgr
else:
    from networkmgr import NetworkMgr
gc.collect()

import colors

#from umdc.status import UmdcEvents, UmdcStatus
from umdc.status import *

if PINOUT.IMPORT_FROM_APP:
    import frozen.umdc_config as CFG
    gc.collect()

    #import umdc.mb_task as mb_task
    from app.umdc.mqtt_task import MqttTask
    gc.collect()
    import app.umdc.mb_task as mb_task
    gc.collect()
else:
    import umdc_config as CFG
    gc.collect()

    #import umdc.mb_task as mb_task
    from umdc.mqtt_task import MqttTask
    gc.collect()
    import umdc.mb_task as mb_task
    gc.collect()

from time_it import asynctimeit, timed_function
gc.collect()

micropython.alloc_emergency_exception_buf(100)




_do_cycle_requested = False
_do_cycle_request_ts = utime.ticks_ms()

_logger = logging.getLogger("Core")
_logger.setLevel(logging.DEBUG)

_control_sleep_lock = asyncio.Lock()

gc.enable()

CONST_CYCLE_FORCE_SOIL_MOISTURE_READ = True


_umdc = None




def handle_timer_interrupt(timer):
    global _umdc
    global _do_cycle_requested
    global _do_cycle_request_ts
    global _logger

    ts_now_ticks_ms = utime.ticks_ms()
    if _do_cycle_requested is False:
        # Normal operation
        _do_cycle_requested = True
        _do_cycle_request_ts = ts_now_ticks_ms
    else:
        # We have not finished the previous do_cycle
        elapsed_s = (utime.ticks_diff(ts_now_ticks_ms, _do_cycle_request_ts))/1000
        if elapsed_s > PINOUT.DO_CYCLE_BUSY_LIMIT_S:
            # This is not good, reset
            _logger.error("WARNING: Elapsed {e} [s] since last do_cycle request and flag is still not cleared! -> Reset".format(e=elapsed_s))

            # NOTE: MCP reset is done with nRST signal from CPU

            machine.reset()



class UmdcCore(object):

    cycle_counter = 0


    tim = Timer(0)


    rtc = machine.RTC()
    status = UmdcStatus(rtc)
    print ("UmdcCore: UmdcStatus created")
    wdt = None

    get_headers = {"Connection": "close"}
    post_headers = {
        'content-type': 'application/json',
        "Connection": "close"
        }



    flag_get_params = False
    flag_post_status_and_events = False

    reasons = []
    reason = ""

    tasks = {}

    # Set attribute so it can be used by other classes
    logger = _logger

    comm_enabled = True
    mqttTaskObj = None

    tools.free()

    print ("UmdcCore: create RTC")
    _rtc = machine.RTC()
    print ("UmdcCore: Get NetworkMgr")
    networkMgr = NetworkMgr
    print ("UmdcCore: Get mb_task")
    mb_task = mb_task
    
    

    print ("UmdcCore: Configure inputs and outputs")
    
    if PINOUT.DI_220VAC is not None:
        print ("UmdcCore: Configure DI_220VAC")
        di_220vac = machine.Pin(PINOUT.DI_220VAC, machine.Pin.IN, pull=None)
    else:
        di_220vac = None
        
    
    if PINOUT.DI1 is not None:
        print ("UmdcCore: Configure DI1")
        di1 = machine.Pin(PINOUT.DI1, machine.Pin.IN, pull=None)
    else:
        di1 = None
    
    
    if PINOUT.DI2 is not None:
        print ("UmdcCore: Configure DI2")
        di2 = machine.Pin(PINOUT.DI2, machine.Pin.IN, pull=None)
    else:
        di2 = None
        
    
    if PINOUT.AI1 is not None:
        print ("UmdcCore: Configure AI1")
        ai1 = machine.ADC(PINOUT.AI1)
        ai1.atten(machine.ADC.ATTN_11DB)        #Full range: 3.3v
    else:
        ai1 = None
        
    
    if PINOUT.AI2 is not None:  
        print ("UmdcCore: Configure AI2")  
        ai2 = machine.ADC(PINOUT.AI2)
        ai2.atten(machine.ADC.ATTN_11DB)        #Full range: 3.3v
    else:
        ai2 = None
    
    
    if PINOUT.DO1 is not None:    
        print ("UmdcCore: Configure DO1")
        do1 = machine.Pin(PINOUT.DO1, machine.Pin.OUT) if PINOUT.DO1 else None
    else:
        do1 = None
        
    if PINOUT.DO2 is not None: 
        print ("UmdcCore: Configure DO2")   
        do2 = machine.Pin(PINOUT.DO2, machine.Pin.OUT) if PINOUT.DO2 else None
    else:
        do2 = None

    print ("UmdcCore: Inputs and outputs configuration finished")
    _imei = None
    _iccid = None
    _revison = None
    _rssi = None

    
    #tools.free()
    print ("UmdcCore: end of class creation")


    @classmethod
    async def update_mb_slave_fail(cls, new_mb_slave_fail):
        if new_mb_slave_fail != cls.status.mb_slave_fail:
            cls.status.mb_slave_fail = new_mb_slave_fail
            cls.mqttTaskObj.set_send_status()

    @classmethod
    def command_outputs(cls, d):
        _logger.debug("CORE.command_outputs {d}".format(d=str(d)))
        if cls.do1: cls.do1.value(d['output_1'])
        if cls.do2: cls.do2.value(d['output_2'])

    @classmethod
    def set_modbus_debug(cls, l):
        cls.mb_task.set_modbus_debug(l)

    @classmethod
    async def modbus_request(cls, request):
        await mb_task.mb_request(request)


    @classmethod
    async def modbus_response(cls, response):
        await cls.mqttTaskObj.send_modbus_response(response)

    @classmethod
    async def modbus_report(cls, li_responses):
        ts = await cls.get_ts_2019()
        await cls.mqttTaskObj.send_report(ts, li_responses)

    @classmethod
    async def get_ts_2019(cls):
        ts_2019_origin = utime.mktime((2019,1,1,0,0,0,0,0))
        ts_now = utime.time()
        elapsed_since_2019_s = ts_now - ts_2019_origin
        return elapsed_since_2019_s

    @classmethod
    async def set_clock(cls, elapsed_since_2019_s):
        ts_2019_origin = utime.mktime((2019,1,1,0,0,0,0,0))
        ts_now = ts_2019_origin + elapsed_since_2019_s
        tm = utime.gmtime(ts_now)
        tm = tm[0:3] + (0,) + tm[3:6] + (0,)
        _logger.debug("set_clock(elapsed_since_2019_s = {e}) -> ts_2019_origin = {o} ts_now = {n} -> gmtime = '{gm}'".format(
            e = elapsed_since_2019_s,
            o = ts_2019_origin,
            n = ts_now,
            gm = str(tm)
            ))
        cls._rtc.datetime(tm)
        

    @classmethod
    def read_and_average(cls, ai):
        n = 100
        v = float(0)
        for i in range(n):
            v = v + ai.read()
        v = v / n
        return v

    @classmethod
    def get_di(cls):
        pass
        
        # Remove flow data to avoid frequent updates when pumping water
        result = (
            cls.di_220vac.value() if cls.di_220vac is not None else 0,
            cls.di1.value() if PINOUT.DI_ENABLED and cls.di1 is not None else 0,
            cls.di2.value() if PINOUT.DI_ENABLED and cls.di2 is not None else 0,
            cls.read_and_average(cls.ai1) if PINOUT.AI_ENABLED and cls.ai1 is not None else 0,
            cls.read_and_average(cls.ai2) if PINOUT.AI_ENABLED and cls.ai2 is not None  else 0
                )
        #cls.status.door_open = door_is_open

        return result




    @classmethod
    async def do_cycle(cls):
        global _do_cycle_requested
        do_cycle_start_us = utime.ticks_us()
        #_logger.debug("Do_cycle start")

        ts_now = utime.time()

        #await cls.do_power_measure()

        cls.cycle_counter += 1

        if False:
            if cls.cycle_counter > PINOUT.MAX_CYCLE_COUNTER:
                _logger.error("Cycle counter has reached {v} -> reset the CPU".format(v=cls.cycle_counter))
                # Need to post in order to clear lists and reduce size
                #await COMM.post_status_and_events(cls, True)

                # Stop mqtt task
                cls.mqttTaskObj.stop()
                
                # Stop network
                stop_event = NetworkMgr.stop_event()
                NetworkMgr.stop()
                try:
                    await asyncio.wait_for_ms(stop_event.wait(), 2000)
                except:
                    # Power off manually
                    _logger.info("Failed to stop NetworkMgr. Disconnect WiFi and poweroff modem ...")
                    await NetworkMgr.hard_stop()
                
                time.sleep(1)
                machine.reset()

        # Check status
        cls.status.check_status()



        # Clear the request flag in a critical section with interrupts disabled
        #s=machine.disable_irq()
        _do_cycle_requested = False
        #machine.enable_irq(s)

        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()

        try:
            if PINOUT.DEBUG_MEM_IN_DO_CYCLE:
                fm = gc.mem_free()
                su = micropython.stack_use()
                mi = micropython.mem_info()
                delta = utime.ticks_diff(utime.ticks_us(), do_cycle_start_us)
                _logger.debug("Do_cycle finished - elapsed {e_do_cycle_ms} [ms] - Free memory {fm} - Stack use {su}".format(
                    e_do_cycle_ms=delta/1000, fm=fm, su=su
                    ))
        except:
            pass


    @classmethod
    def read_inputs(cls):
        # Get digital inputs
        di_values = cls.get_di()
        
        _connection_str = cls.networkMgr.connection_str()
        
        # Update status
        hasChanged = cls.status.set_di(di_values, _connection_str)

        if hasChanged:
            # Send event
            cls.flag_post_status_and_events = True
            # Send status
            if cls.mqttTaskObj is not None:
                cls.mqttTaskObj.set_send_status()

   
    @classmethod
    async def init(cls):
        global _di_flow_interrupt_received
        global _di_flow_interrupt_pin
        global _umdc

        _umdc = cls

        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)
        else:
            cls.wdt = None


            
        #mb_task.init_mb_task(cls)
            

        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()

        #
        # Check filesystem usage
        #

        try:
            s = os.statvfs('/')
            total_bytes = s[0]*s[2]
            free_bytes = s[1]*s[3]
            used_bytes = total_bytes-free_bytes
            _logger.debug("FileSystem: Total {t}, free {f}, used {u}".format(t=total_bytes, f=free_bytes, u=used_bytes))

        except Exception as ex:
            pass

        cls.read_inputs()


    @classmethod
    def setup_interrupts(cls):
        
        # Note: urequests timeout is 30s and there is no way to decrease it
        # therefore wdt must be larger -> 60s?
        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)

        cls.tim.init(period=PINOUT.CYCLE_PERIOD_MS, mode=machine.Timer.PERIODIC, callback=handle_timer_interrupt)        # create the interrupt

    @classmethod
    def disable_interrupts(cls):
        cls.tim.deinit()
    


    @classmethod
    async def comm_task(cls):
        _logger.debug("Platform communication TASK started")
        while cls.comm_enabled:


            try:
                if cls.flag_post_status_and_events:
                    cls.flag_post_status_and_events = False
                    #await COMM.post_status_and_events(cls, force_post=False)
                    if PINOUT.WDT_ENABLED:
                        cls.wdt.feed()
                    await asyncio.sleep_ms(100)
            except Exception as ex:
                _logger.exc(ex,"Failed to post status and events: {e}".format(e=ex))


            try:
                tr = logging.get_traces()
                if len(tr)>0:
                    #await COMM._post_traces(cls)
                    if PINOUT.WDT_ENABLED:
                        cls.wdt.feed()
                    await asyncio.sleep_ms(100)
            except Exception as ex:
                _logger.exc(ex,"Failed to post traces: {e}".format(e=ex))


            # Wait for 4 seconds, but only if the flag is clear
            for j in range(20):
                await asyncio.sleep(0.2)
                if cls.flag_post_status_and_events:
                    break
                if not cls.comm_enabled:
                    break

        _logger.debug("Platform communication TASK finished")
        



    @classmethod
    async def cycle_task(cls):
        global _do_cycle_requested
        global _do_cycle_request_ts
        _logger.debug("Cycle TASK started")
        while cls.comm_enabled:
            try:
                if _do_cycle_requested:
                    #_do_cycle_requested = False
                    await cls.do_cycle()
            except Exception as ex:
                _logger.exc(ex,"Failed to do_cycle: {e}".format(e=ex))

            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            await asyncio.sleep_ms(1000)
        _logger.debug("Cycle TASK finished")


    @classmethod
    async def wait_event_and_show_connection(cls, event):
        await event.wait()
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()

    @classmethod
    async def connection_control(cls):
        event = NetworkMgr.connection_event()
        await cls.wait_event_and_show_connection(event)
        event = NetworkMgr.time_setup_event()
        await cls.wait_event_and_show_connection(event)


    @classmethod
    async def update_modbus_messages(cls, d):
        _logger.debug("CORE.update_modbus_messages with '{d}'".format(d=str(d)))

    @classmethod
    async def main(cls, is_interrupt=False, porta=0):

        cls.mqttTaskObj = MqttTask(cls, cls.status, NetworkMgr)

        await cls.init()
        cls.setup_interrupts()
        

        _logger.debug("Free memory: {f}".format(f=gc.mem_free()))

        if is_interrupt:
            _logger.info("Wakeup with interrupt")

            #await COMM.post_status_and_events(cls, force_post=True)
            # Send the event
            #await COMM.post_events(cls)


        _logger.debug("Start main loop ...")

        ts_last_gc = utime.time()

        cls.tasks["cycle"] = asyncio.create_task(cls.cycle_task())
        if PINOUT.MB_ENABLED:
            cls.tasks["mb"] = asyncio.create_task(mb_task.mb_task(cls))
            
        cls.tasks["comm"] = asyncio.create_task(cls.comm_task())
        #cls.tasks["pump"] = asyncio.create_task(control_task.pump_control_task(cls))
        #cls.tasks["networkmgr"] = asyncio.create_task(NetworkMgr.nmtask())
        cls.tasks["connection_ctrl"] = asyncio.create_task(cls.connection_control())

 
        cls.tasks["mqtt"] = asyncio.create_task(cls.mqttTaskObj.mqtt_task())

        while True:

            try:
                # always read io in every loop cycle
                cls.read_inputs()
            except Exception as ex:
                _logger.exc(ex,"Failed to read_inputs: {e}".format(e=ex))


            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()

            ts_now = utime.time()

            gc_elapsed_s = ts_now - ts_last_gc
            if gc_elapsed_s > 600:
                ts_last_gc = ts_now
                _logger.debug("Run GC")
                # Run Garbage Collector
                gc.collect()
                #gc.threshold(gc.mem_free() // 4 + gc.mem_alloc())
                
                tools.free(True)
                
            # Let the system do house keeping
            # Do not use utime.sleep_ms because it blocks serial port reading
            #utime.sleep_ms(350)
            await asyncio.sleep_ms(1000)

        for n,t in cls.tasks.items():
            _logger.debug("Cancel task {n}".format(n=n))
            t.cancel()



    @classmethod
    def cb_feed(cls):
        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)

   
   
    @classmethod
    async def do_reset(cls, hard=True):
        ts_now = utime.time()
        control_sleep_debug = logging.DEBUG
        if control_sleep_debug<=logging.DEBUG:
            _logger.debug("do_reset(now={t})".format(t=ts_now))

        await _control_sleep_lock.acquire()

        _logger.debug("{g}------------- PREPARE FOR RESET ---------------{n}".format(g=colors.BOLD_GREEN, n=colors.NORMAL))

        # Disable any further communication
        try:
            cls.comm_enabled = False
            #COMM.disable()
        except Exception as ex:
            _logger.exc(ex,"Failed to disable comms", nopost=True)
            pass

        # Prepare to reset
        try:
            cls.status.store_status()
        except Exception as ex:
            _logger.exc(ex,"Failed to store status", nopost=True)
            pass


        # Stop network
        try:
            try:
                stop_event = cls.networkMgr.stop_event()
                cls.networkMgr.stop()

                try:
                    await asyncio.wait_for_ms(stop_event.wait(), 12000)
                except Exception as ex:
                    # Power off manually
                    _logger.exc(ex, "Failed to stop NetworkMgr. Disconnect WiFi and poweroff modem ...", nopost=True)
                    
                    try:
                        await asyncio.wait_for(ls.networkMgr.hard_stop(), timeout = 5)
                    except asyncio.TimeoutError:
                        pass
                    
            except Exception as ex:
                # Power off manually
                _logger.exc(ex, "Failed to stop NetworkMgr. Disconnect WiFi and poweroff modem ...", nopost=True)
                try:
                    await asyncio.wait_for(ls.networkMgr.hard_stop(), timeout = 5)
                except asyncio.TimeoutError:
                    pass
        except:
            # Just go on with power down
            pass


        try:
            #await cls.enable_power(False)
            pass
        except Exception as ex:
            _logger.exc(ex,"Failed to disable load's power lines", nopost=True)
            pass

        # Shut down MODBUS and release UART
        try:
            _logger.debug("Release modbus")
            cls.mb_task.release_mb_sensor()
        except Exception as ex:
            _logger.exc(ex,"Failed to release the modbus sensor", nopost=True)
            pass

        

        if PINOUT.WDT_ENABLED:
            wdt_time_s = 300
            try:
                cls.wdt = machine.WDT(timeout=wdt_time_s*1000)
            except Exception as ex:
                _logger.exc(ex,"Failed to set WDT to {s} before reset".format(s=wdt_time_s), nopost=True)

        

        # Allow time to print the debug output and disconnect wlan
        time.sleep(1)

        #
        # Final adjustment of time to sleep
        #


        _logger.debug("=============================================")
        _logger.debug("RESET")
        _logger.debug("=============================================")

        # Allow time to complete changes
        time.sleep(2)

        if hard:
            machine.reset()
        else:
            #sys.exit()
            machine.deepsleep(500)


        _control_sleep_lock.release()


