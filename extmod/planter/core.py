import time
import os
import io
import sys

import logging

import json
import esp32
import machine
import gc
from machine import Pin, sleep, time_pulse_us, disable_irq, enable_irq, Timer, WDT
from planter.config import K_WAKENING_PERIOD

import uasyncio as asyncio

import micropython


import utime
import ubinascii
import ujson

import hwversion


from networkmgr import NetworkMgr

import ssd1306
import mcp23017
import adxl34x
#from frozen import adxl34x as adxl34x
import soil_moisture as SM

from ina3221 import INA3221

import power_monitor as power_monitor

import colors

#from planter.status import PlanterEvents, PlanterStatus
from planter.status import *
import planter_pinout as PINOUT
import planter.comm as COMM
import planter.display as PL_DISPLAY


import planter.control_task as control_task
import planter.sm_task as sm_task
import planter.flow as flow
import ulp.ulp_pulse as ulp_pulse


from time_it import asynctimeit, timed_function

micropython.alloc_emergency_exception_buf(100)


_do_cycle_requested = False
_do_cycle_request_ts = utime.ticks_ms()
_dia_interrupt_flag = False
_dia_interrupt_pin = 0

_logger = logging.getLogger("Core")
_logger.setLevel(logging.DEBUG)


gc.enable()

CONST_CYCLE_FORCE_SOIL_MOISTURE_READ = True


_planter = None



def handle_dia_interrupt(pin):
    global _planter
    global _dia_interrupt_flag
    global _dia_interrupt_pin
    #print ("Schedule handle_dia_interrupt")
   
    # Schedule only if the previous interrupt has been handled
    if _dia_interrupt_flag is False:
        _dia_interrupt_flag = True
        _dia_interrupt_pin = pin

        #print("DIA_INT")
        try:
            micropython.schedule(_planter.handle_dia_interrupt, pin)
        except Exception as ex:
            print("Failed to schedule _planter.handle_dia_interrupt: {e}".format(e=str(ex)))

    


def handle_timer_interrupt(timer):
    global _planter
    global _do_cycle_requested
    global _do_cycle_request_ts
    global _logger

    _planter.process_pulses()

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



class Planter(object):

    cycle_counter = 0

    if hwversion.HW_VERSION == hwversion.VERSION_TCALL_14:
        dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=Pin.PULL_DOWN)
    else:
        #dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=None)
        dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=Pin.PULL_DOWN)
    
    # Note: MPS reset is done with nRST signal from the CPU

    tim = Timer(0)
    i2c = None
    ina3221_12v = None
    ina3221_5v = None

    mcp = None
    accelerometer = None

    rtc = machine.RTC()
    status = PlanterStatus(rtc)
    wdt = None

    dia_interrupt_received = False
    dia_interrupt_pin = None

    get_headers = {"Connection": "close"}
    post_headers = {
        'content-type': 'application/json',
        "Connection": "close"
        }



    flag_start_pump = False
    flag_stop_pump = False

    flag_get_params = False
    flag_post_status_and_events = False

    reasons = []
    reason = ""

    tasks = {}
    mcp_lock = asyncio.Lock()

    calendar_data = None
    ts_last_power_monitor = 0

    # Set attribute so it can be used by other classes
    logger = _logger

    comm_enabled = True

    @classmethod
    def clear_pulses():
        global _pulses
        _pulses = 0

    @classmethod
    def get_pulses():
        global _pulses
        return _pulses

    @classmethod
    async def enable_pump(cls, value, reason):
        await cls.mcp_lock.acquire()
        if cls.status.has_mcp:
            if value:
                cls.mcp.portb.gpio |= PINOUT.DO_B_PUMP_BIT
            else:
                cls.mcp.portb.gpio &= ~PINOUT.DO_B_PUMP_BIT
        cls.status.set_pump_status(value, reason)
        cls.mcp_lock.release()

    @classmethod
    def get_pump_status(cls):
        if cls.status.has_mcp:
            pump_status = ((cls.mcp.portb.gpio & PINOUT.DO_B_PUMP_BIT) == PINOUT.DO_B_PUMP_BIT)
            cls.status.set_pump_status(pump_status, "Read from GPIO")
        else:
            # Simulated
            pump_status = cls.status.pump_on
        return pump_status

    @classmethod
    async def enable_power(cls, value):
        has_changed = False
        await cls.mcp_lock.acquire()
        if cls.status.has_mcp:
            c = cls.mcp.portb.gpio
        else:
            # Simulated
            c = PINOUT.DO_B_POWER_BITS
        n = c
        if value:
            n |= PINOUT.DO_B_POWER_BITS
        else:
            n &= ~PINOUT.DO_B_POWER_BITS
        if c != n:
            if cls.status.has_mcp:
                cls.mcp.portb.gpio = n
            _logger.debug("{s} 3V, 5V and 12V power lines".format(s="Enable" if value else "Disable"))
            has_changed = True
        cls.status.load_3v_on=value
        cls.status.load_5v_on=value
        cls.status.load_12v_on=value
        cls.mcp_lock.release()
        return has_changed

    @classmethod
    async def set_water_level_sensor_mode(cls, mode):
        current_value = cls.mcp.portb.gpio
        if mode:
            cls.mcp.portb.gpio = current_value | PINOUT.DO_B_LEVEL_MODE
        else:
            cls.mcp.portb.gpio = current_value & ((~PINOUT.DO_B_LEVEL_MODE) &0xFF)

    @classmethod
    async def detect_water_level_sensor(cls):

        b_detected = False
        if cls.status.has_mcp:
            # Backup original value
            b_orig = cls.mcp.portb.gpio
            cls.mcp.portb.gpio = 0x0E

            for i in range(20):
                # Switch mode line
                cls.set_water_level_sensor_mode(True)
                await asyncio.sleep_ms(50)
                a_mode_1 = cls.mcp.porta.gpio
                l_mode_1 = ((a_mode_1&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE

                cls.set_water_level_sensor_mode(False)
                await asyncio.sleep_ms(50)
                a_mode_0 = cls.mcp.porta.gpio
                l_mode_0 = ((a_mode_0&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE

                if l_mode_0 != l_mode_1:
                    b_detected = True
                    break
                
            # Compare
            if b_detected:
                _logger.info("WaterLevel sensor detected.")
            else:
                _logger.error("Failed to detect WaterLevel sensor.")
            
            # Restore original value
            cls.mcp.portb.gpio = b_orig
        return b_detected



    @classmethod
    def get_di(cls):
        if cls.status.has_mcp:
            a = cls.mcp.porta.gpio
            b = cls.mcp.portb.gpio
        else:
            a = 0
            b = 0

        if cls.status.load_5v_on:
            ll = ((a&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE
        else:
            # 5v loads are not powered, so we cannot read level_low -> keep previous value
            ll = cls.status.level_low

        # High -> door is open (switch is open and signal is pull up by MBP23017)
        # Low -> door is closed (switch is closed and signal is connected to GND)
        door_is_open = (a&PINOUT.DI_A_DOOR_BIT) == PINOUT.DI_A_DOOR_BIT

        # Remove flow data to avoid frequent updates when pumping water
        result = (
                    #(a&PINOUT.DI_A_FLOW_BIT) == PINOUT.DI_A_FLOW_BIT,
                    0,
                    (a&PINOUT.DI_A_RAIN_BIT) == PINOUT.DI_A_RAIN_BIT,
                    door_is_open,
                    ll,
                    (a&PINOUT.DI_A_ACC_INT1_BIT) == PINOUT.DI_A_ACC_INT1_BIT,
                    (a&PINOUT.DI_A_ACC_INT2_BIT) == PINOUT.DI_A_ACC_INT2_BIT,
                    (a&PINOUT.DI_A_BUTTON_1) == PINOUT.DI_A_BUTTON_1,
                    (a&PINOUT.DI_A_NSMBALERT) == PINOUT.DI_A_NSMBALERT,
                    (a&PINOUT.DI_A_SOCALERT) == PINOUT.DI_A_SOCALERT,
                a,
                b
                )
        cls.status.door_open = door_is_open

        if cls.status.load_5v_on:
            cls.status.level_low = ll
        else:
            # 5v loads are not powered, so we cannot read level_low
            pass

        return result

    @classmethod
    def configure_mcp(cls, addr=0x20):
        if cls.status.has_mcp:
            cls.mcp = mcp23017.MCP23017(cls.i2c, addr)
            cls.mcp.mode = PINOUT.MCP_MODE
            cls.mcp.gpio = PINOUT.MCP_GPIO_INIT
            cls.mcp.pullup = PINOUT.MCP_PULLUP

            if hwversion.HW_VERSION == hwversion.VERSION_TCALL_14:
                cls.mcp.config(interrupt_polarity=0, interrupt_mirror=1)
            elif hwversion.HW_VERSION == hwversion.VERSION_TCALL_MPU:
                cls.mcp.config(interrupt_open_drain=1, interrupt_mirror=1)
            elif hwversion.HW_VERSION == hwversion.VERSION_10:
                cls.mcp.config(interrupt_polarity=1, interrupt_open_drain=0, interrupt_mirror=1)

            cls.mcp.porta.interrupt_enable = PINOUT.MCP_A_INTERRUPT_ENABLE
            cls.mcp.portb.interrupt_enable = PINOUT.MCP_B_INTERRUPT_ENABLE

    @classmethod
    def init_adxl34x(cls, addr=0x53):
        _logger.debug("Create ADXL345 accelerometer driver")
        cls.accelerometer = adxl34x.ADXL345(cls.i2c)
        cls.accelerometer.sensorMotion()
        
        r = cls.accelerometer.data_format
        _logger.debug("ADXL345 data format: {r}".format(r=r))

        r = str(cls.accelerometer.enabled_interrupts)
        _logger.debug("ADXL345 enabled interrupts: {r}".format(r=r))
        
        r = str(cls.accelerometer.interrupt_map)
        _logger.debug("ADXL345 interrupt map: {r}".format(r=r))
        
        r = str(cls.accelerometer.thresholds)
        _logger.debug("ADXL345 thresholds: {r}".format(r=r))

        
        cls.status.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP = PINOUT.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP_ADXL

    @classmethod
    def init_mc34x9(cls, addr=76):
        from mc3479 import MC34X9, MC34X9_sr_t, enableFIFO, enableFifoThrINT, MC34X9_range_t
        _logger.debug("Create MC34X9 accelerometer driver")
        cls.accelerometer = MC34X9(bSpi = True, chip_select=None, drv=cls.i2c, i2c_address=addr)
        cls.accelerometer.sensorMotion(enableTILT=False, enableFLIP=False, enableANYM=True, enableSHAKE=False, enableTILT35=False)
        cls.status.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP = PINOUT.MCP_A_INTERRUPT_ENABLE_FOR_WAKEUP


    @classmethod
    def init_mcp(cls):
        # Enable MCP
        # NOTE: MCP reset is done with nRST signal from CPU, so it is already enabled when CPU starts

        # Create I2C driver
        cls.i2c = machine.SoftI2C(scl=machine.Pin(PINOUT.I2C_SCL), sda=machine.Pin(PINOUT.I2C_SDA))

        if PINOUT.SCAN_I2C:
            _logger.debug("Scan I2C ...")
            i2c_devices = cls.i2c.scan()

            d_devices = {
                32: "MCP23017 IO",
                36: "PN532 NFC",
                52: "Power Management AXP192",
                60: "SSD1306 screen controller",
                64: "INA 3221 PV-BATT-12V",
                65: "INA 3221 5V",
                69: "INA 226",
                76: "MC3479 accelerometer",
                83: "ADXL343/ADXL345 accelerometer",
                117: "Power Management SIL2104",
            }

            for d in i2c_devices:
                if d in d_devices:
                    _logger.debug("{a} -> {b}".format(a=d, b=d_devices[d]))
                    if d == 32:
                        cls.status.has_mcp = True
                    if d == 64:
                        cls.status.has_ina3221_12v = True
                    if d == 65:
                        cls.status.has_ina3221_5v = True
                    if d == 69:
                        cls.status.has_ina226 = True
                    if d == 60:
                        cls.status.has_display = True
                    if d == 76:
                        cls.status.has_accelerometer = True
                        cls.status.accelerometer_model.append("mc3479")
                    if d == 83:
                        cls.status.has_accelerometer = True
                        cls.status.accelerometer_model.append("adxl34x")
                else:
                    _logger.debug("{a} -> UNKNOWN".format(a=d))

        # Activate alarms if we failed to detect the power monitor or the accelerometer
        cls.status.data.alarm_powermonitor = cls.status.has_ina3221_12v is False
        cls.status.data.alarm_accel =  cls.status.has_accelerometer is False

        if cls.status.has_ina3221_12v is False:
            cls.status.add_event(PlanterEvents.Power_Monitor, PlanterEvents.VALUE_LOW, 
            "Failed to read the 12V power monitor -> Cannot read battery, pv and pump power")

        cls.configure_mcp(0x20)


    @classmethod
    def process_pulses(cls):
        global _do_cycle_requested

        pulse_count = flow.pulse_count()
        (flow_lpm, pulses_per_second, flow_count_last_period) = flow.flow_lpm()

        # Update status
        cls.status.flow_lpm = flow_lpm
        cls.status.pps = pulses_per_second
        cls.status.pulse_count = pulse_count

    @classmethod
    async def do_power_measure(cls):
        ts_now = utime.time()

        try:
            if cls.status.load_3v_on:
                # Read INA
                e = ts_now - cls.ts_last_power_monitor
                pump_on = cls.status.pump_on
                if (e >= 15) and (pump_on is False):
                    cls.ts_last_power_monitor = ts_now
                    r_pm = await power_monitor.cycle(False)
                    #_logger.debug("add_power_measure {s}".format(s=str(r_pm)))
                    cls.status.add_power_measure(r_pm)
            else:
                # power on the 3.3V loads line is off, so the INA is not going to answer
                _logger.debug("3.3v load line is power off -> power monitor is power off -> skip reading the power monitor")
                pass
        except Exception as ex:
            _logger.exc(ex,"power_monitor error: {e}".format(e=str(ex)))

    @classmethod
    async def do_cycle(cls):
        global _do_cycle_requested
        do_cycle_start_us = utime.ticks_us()
        #_logger.debug("Do_cycle start")

        ts_now = utime.time()

        await cls.do_power_measure()

        cls.cycle_counter += 1

        if cls.cycle_counter > PINOUT.MAX_CYCLE_COUNTER:
            _logger.error("Cycle counter has reached {v} -> reset the CPU".format(v=cls.cycle_counter))
            # Need to post in order to clear lists and reduce size
            await COMM.post_status_and_events(cls, True)

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

        # Update display
        try:
            PL_DISPLAY.update_display_with_status(cls)
        except Exception as ex:
            _logger.exc(ex,"failed to update display: {e}".format(e=str(ex)))


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
    def check_accelerometer_events(cls):
        if cls.status.has_accelerometer:
            retCode = True
            aux_n = 0
            while retCode and aux_n < 100:
                (retCode, impact_str) = cls.accelerometer.interruptChecker()
                if retCode:
                    cls.status.add_event(PlanterEvents.Impact_Detected, PlanterEvents.STATUS_ON,impact_str)
                    cls.logger.debug(impact_str)
                aux_n = aux_n + 1

    @classmethod
    def handle_dia_interrupt(cls, pin):
        global _dia_interrupt_flag
        _dia_interrupt_flag = False
        cls.dia_interrupt_received = True
        cls.dia_interrupt_pin = pin

        current_page = cls.status.display_page

        if cls.dia_interrupt.value() is False:
            if cls.status.has_mcp:
                a=cls.mcp.porta.gpio
                b=cls.mcp.portb.gpio
            else:
                a = 0
                b = 0
            _logger.debug('DIA interrupt: pin {p} -> A = {a:08b}  B = {b:08b}'.format(
                p=cls.dia_interrupt_pin, a=a, b=b))
        # Get digital inputs
        di_values = cls.get_di()
        # Update status
        hasChanged = cls.status.set_di(di_values)


        if di_values is not None and (di_values[PINOUT.ACC_INT1_IDX] or di_values[PINOUT.ACC_INT2_IDX]):
            cls.check_accelerometer_events()


        new_page = cls.status.display_page
        if new_page != current_page:
            # update display
            PL_DISPLAY.update_display_with_status(cls)

        # Clear interrupt
        if cls.status.has_mcp:
            cls.mcp_flagged = cls.mcp.porta.interrupt_flag
            cls.mcp_captured = cls.mcp.porta.interrupt_captured
        else:
            cls.mcp_flagged = False
            cls.mcp_captured = False

        if hasChanged:
            # Send event
            cls.flag_post_status_and_events = True

   
    @classmethod
    async def init(cls):
        global _di_flow_interrupt_received
        global _di_flow_interrupt_pin
        global _planter

        _planter = cls

        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)
        else:
            cls.wdt = None

        cls.init_mcp()
        await cls.enable_power(True)

        # Check if there is a water level sensor attached and working
        #b_water_level_sensor_detected = await cls.detect_water_level_sensor()
        b_water_level_sensor_detected = True
        cls.status.water_level_sensor_detected = b_water_level_sensor_detected
        cls.set_water_level_sensor_mode(False)

        power_monitor.init(cls.i2c, ["12v"])

        if cls.status.has_display:
            PL_DISPLAY.init_display(cls.i2c)
            
        sm_task.init_sm_sensor(cls)
        if cls.status.has_accelerometer:
            if "adxl34x" in cls.status.accelerometer_model:
                # Priority to adxl34x model if both are mounted
                cls.init_adxl34x()
            
            elif "mc3479" in cls.status.accelerometer_model:
                cls.init_mc34x9()
            

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
            PL_DISPLAY.update_display([["FileSystem:",
                                "total {t:>7}".format(t=total_bytes),
                                "free {t:>7}".format(t=free_bytes),
                                "used {t:>7}".format(t=used_bytes),
                                None], True])
        except Exception as ex:
            pass

        cls.handle_dia_interrupt(PINOUT.DIA_INTERRUPT)


    @classmethod
    def setup_interrupts(cls):
        
        #flow.setup_interrupts()

        if hwversion.HW_VERSION == hwversion.VERSION_TCALL_14:
            cls.dia_interrupt.irq(trigger=PINOUT.FLOW_IRQ_MODE, handler=handle_dia_interrupt)
        else:
            cls.dia_interrupt.irq(trigger=PINOUT.FLOW_IRQ_MODE, handler=handle_dia_interrupt)
        # Clear previous interrupt if any
        if cls.status.has_mcp:
            v = cls.mcp.porta.interrupt_captured
            v = cls.mcp.portb.interrupt_captured
            v = cls.mcp.porta.interrupt_flag
            v = cls.mcp.portb.interrupt_flag

        #print("PortA IntCon: {0:b}".format(cls.mcp.porta.interrupt_compare_default))
        #print("PortA IOConfig: {0:b}".format(cls.mcp.porta.io_config))
        #print("PortA IntEn: {0:b}".format(cls.mcp.porta.interrupt_enable))
        #print("PortB IntCon: {0:b}".format(cls.mcp.portb.interrupt_compare_default))
        #print("PortB IOConfig: {0:b}".format(cls.mcp.portb.io_config))
        #print("PortB IntEn: {0:b}".format(cls.mcp.portb.interrupt_enable))

        # Note: urequests timeout is 30s and there is no way to decrease it
        # therefore wdt must be larger -> 60s?
        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)

        cls.tim.init(period=PINOUT.CYCLE_PERIOD_MS, mode=machine.Timer.PERIODIC, callback=handle_timer_interrupt)        # create the interrupt

    @classmethod
    def disable_interrupts(cls):
        #flow.disable_interrupts()
        cls.dia_interrupt.irq(trigger=0)
        cls.tim.deinit()
    

    @classmethod
    async def set_sensor_motion_threshold(cls, factor=1):
        try:
            got_params = await COMM.do_get_params(cls)
            if got_params:
                if cls.status.has_accelerometer:
                    # Update accelerometer motion configuration
                    p = CFG.params()
                    advanced = p[CFG.K_ADVANCED]
                    if CFG.K_ADV_ACC_MOTION_THRESHOLD_G in advanced:
                        th = float(advanced[CFG.K_ADV_ACC_MOTION_THRESHOLD_G])
                    else:
                        th = float(PINOUT.DEFAULT_ACC_MOTION_TH)
                    th = th * float(factor)
                    try:
                        # Use new functionality
                        cls.accelerometer.sensorImpactThreshold(th)
                    except:
                        # Fall back to previous functionality
                        cls.accelerometer.sensorMotionThreshold(th)
                if cls.status.has_rain_sensor is False:
                    # Set the received rain mmph value, because we do not have a rain sensor
                    cls.status.rain_mmph = float(CFG.params()[CFG.K_RAIN_MMPH])
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            await asyncio.sleep_ms(100)
        except Exception as ex:
            _logger.exc(ex,"Failed to get params: {e}".format(e=ex))    


    @classmethod
    async def comm_task(cls):
        _logger.debug("Platform communication TASK started")
        while cls.comm_enabled:
            if cls.status.pump_on is False:
                # Do not communicate while the pump is ON, to avoid missing timer interrupts
                await cls.set_sensor_motion_threshold(factor=1.0)

                try:
                    if cls.flag_post_status_and_events:
                        cls.flag_post_status_and_events = False
                        await COMM.post_status_and_events(cls, force_post=cls.status.pump_on)
                        if PINOUT.WDT_ENABLED:
                            cls.wdt.feed()
                        await asyncio.sleep_ms(100)
                except Exception as ex:
                    _logger.exc(ex,"Failed to post status and events: {e}".format(e=ex))


                try:
                    tr = logging.get_traces()
                    if len(tr)>0:
                        await COMM._post_traces(cls)
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
    async def webapp_task(cls):
        NetworkMgr.activate_ap()
        import webapp
        webapp.set_planter(cls)
        webapp.start_webapp()
        logging.set_webapp(webapp)
        _logger.debug("Web APP TASK started")

        # Starts the server as easily as possible in managed mode,
        webapp.mws2.StartManaged()

        # Main program loop until keyboard interrupt,
        try :
            while webapp.mws2.IsRunning :
                await asyncio.sleep(4)
        except KeyboardInterrupt :
            pass

        webapp.mws2.Stop()
        _logger.debug('Web APP stopped')


    @classmethod
    async def rain_task(cls):
        await asyncio.sleep_ms(1000) # Give time to the ULP to start
        _logger.debug("Rain TASK started")
        while cls.comm_enabled:
            try:
                duration_h = cls.status.elapsed_since_last_rain_measure_h()
                
                if (duration_h is None) or (duration_h >= PINOUT.RAIN_MEASURES_PERIOD_H):
                    if duration_h is None:
                        duration_h = PINOUT.RAIN_MEASURES_PERIOD_H
                    (pulsesRaw, rain_mm, mmph, shortestPulseRaw, rainDownpour) = ulp_pulse.getRainMeasure(duration_h)
                    cls.status.add_rain_measure(pulsesRaw, mmph)
            except Exception as ex:
                _logger.exc(ex,"Failed to rain_task: {e}".format(e=ex))

            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            await asyncio.sleep_ms(10000)
        _logger.debug("Rain TASK finished")


    @classmethod
    async def wait_event_and_show_connection(cls, event):
        await event.wait()
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        cls.status.display_page = PlanterStatus.PAGE_WIFI
        PL_DISPLAY.update_display_with_status(cls)

    @classmethod
    async def connection_control(cls):
        event = NetworkMgr.connection_event()
        await cls.wait_event_and_show_connection(event)
        event = NetworkMgr.time_setup_event()
        await cls.wait_event_and_show_connection(event)


    @classmethod
    async def main(cls, is_interrupt=False, porta=0):
        global _dia_interrupt_flag
        global _dia_interrupt_pin

        await cls.init()
        await cls.enable_power(True)
        cls.setup_interrupts()
        

        _logger.debug("Free memory: {f}".format(f=gc.mem_free()))

        if is_interrupt:
            _logger.info("Wakeup with interrupt. Port A = 0x{porta:08b}".format(porta=porta))
            if porta & (PINOUT.DI_A_ACC_INT1_BIT | PINOUT.DI_A_ACC_INT2_BIT):
                cls.check_accelerometer_events()
            if porta & (PINOUT.DI_A_DOOR_BIT):
                # Door open
                cls.status.add_event(PlanterEvents.Door_Open, PlanterEvents.STATUS_ON,"Open")

            #await COMM.post_status_and_events(cls, force_post=True)
            # Send the event
            await COMM.post_events(cls)


        _logger.debug("Start main loop ...")

        ts_last_gc = utime.time()

        cls.tasks["cycle"] = asyncio.create_task(cls.cycle_task())
        cls.tasks["sm"] = asyncio.create_task(sm_task.soil_moisture_task(cls))
        cls.tasks["comm"] = asyncio.create_task(cls.comm_task())
        cls.tasks["pump"] = asyncio.create_task(control_task.pump_control_task(cls))
        #cls.tasks["networkmgr"] = asyncio.create_task(NetworkMgr.nmtask())
        cls.tasks["connection_ctrl"] = asyncio.create_task(cls.connection_control())

        if CFG.has_rain_sensor():
            cls.tasks["rain"] = asyncio.create_task(cls.rain_task())

        if PINOUT.WEBAPP_ENABLED:
            cls.tasks["webapp"] = asyncio.create_task(cls.webapp_task())

        while True:

            try:
                if _dia_interrupt_flag:
                    _dia_interrupt_flag = False
                # always read io in every loop cycle
                cls.handle_dia_interrupt(_dia_interrupt_pin)
            except Exception as ex:
                _logger.exc(ex,"Failed to handle dia interrupt: {e}".format(e=ex))


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
                
            # Let the system do house keeping
            # Do not use utime.sleep_ms because it blocks serial port reading
            #utime.sleep_ms(350)
            await asyncio.sleep_ms(350)

        for n,t in cls.tasks.items():
            _logger.debug("Cancel task {n}".format(n=n))
            t.cancel()



    @classmethod
    def cb_feed(cls):
        if PINOUT.WDT_ENABLED:
            cls.wdt = WDT(timeout=PINOUT.WDT_TIMEOUT_MS)

   

