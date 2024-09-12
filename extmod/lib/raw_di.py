
print ("Raw DI: Load libraries")
import gc, sys
import machine
from machine import Pin
from machine import wake_reason
import logging
import ujson
import utime

print ("Raw DI: Load MCP23017")
import hwversion
import mcp23017
import planter_pinout as PINOUT

def raw_di(i2c, check_updates, recheck_water_sensor=0):

    _rtc = machine.RTC()
    # Check if wakeup is because of interrupt of door or accelerometer
    _log = logging.getLogger("di")
    _log.setLevel(logging.DEBUG)


    _is_interrupt = False
    _porta = 0
    _rtc = machine.RTC()
    _fs = None
    _needs_to_check_update = True
    _is_button_pressed = False

    try:

        _pwm_pin = machine.Pin(PINOUT.PWM_OUT, mode=Pin.OUT, value=0)
        _pwm_pin.off()

        _mcp = None
        _porta = None
        _aux_level_low = None

        _wake_reason = machine.wake_reason()
        if _wake_reason == 0x5 or True:
            #_i2c = machine.SoftI2C(scl=machine.Pin(PINOUT.I2C_SCL), sda=machine.Pin(PINOUT.I2C_SDA))
            _i2c=i2c

            try:
                _mcp = mcp23017.MCP23017(_i2c, 0x20)
                if _wake_reason == 0:
                    # Power cycle
                    _mcp.mode = PINOUT.MCP_MODE
                    _mcp.gpio = PINOUT.MCP_GPIO_INIT
                    _mcp.pullup = PINOUT.MCP_PULLUP
                _mcp.porta.interrupt_enable = 0x00
                _mcp.portb.interrupt_enable = 0x00
                
                if (_mcp.portb.gpio & 0x09 ) != 0x00:
                    _log.debug("Disable pump and 12v loads")
                    _mcp.portb.gpio &= 0xF6

                if (_mcp.portb.gpio & 0x06 ) != 0x06:
                    _log.debug("Enable 3.3v and 5v loads")
                    _mcp.portb.gpio |= 0x06 # Reset pump, enable 3.3V and 5V loads, disable 12V loads
                
                

                utime.sleep_ms(150)

                _porta = _mcp.porta.gpio
                _aux_level_low = ((_porta&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE
                if _aux_level_low and recheck_water_sensor>0:
                    _log.debug("Recheck water level sensor to give it time to boot and stabilize - max {n} trials".format(n=recheck_water_sensor))
                    for i in range(recheck_water_sensor):
                        _porta = _mcp.porta.gpio
                        _aux_level_low = ((_porta&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE
                        if _aux_level_low:
                            utime.sleep_ms(100)
                        else:
                            break
            except Exception as ex:
                _log.exc(ex, "Failed to read MCP")
                del _mcp
                _mcp = None


            if hwversion.HW_VERSION == hwversion.VERSION_TCALL_14:
                _dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=Pin.PULL_DOWN)
            else:
                #_dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=None)
                _dia_interrupt = Pin(PINOUT.DIA_INTERRUPT, Pin.IN, pull=Pin.PULL_DOWN)

            _dia_value = _dia_interrupt.value()

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

            if _mcp is not None:
                result = (0,
                            (_porta&PINOUT.DI_A_RAIN_BIT) == PINOUT.DI_A_RAIN_BIT,
                            (_porta&PINOUT.DI_A_DOOR_BIT) == PINOUT.DI_A_DOOR_BIT,
                            ((_porta&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE,
                            (_porta&PINOUT.DI_A_ACC_INT1_BIT) == PINOUT.DI_A_ACC_INT1_BIT,
                            (_porta&PINOUT.DI_A_ACC_INT2_BIT) == PINOUT.DI_A_ACC_INT2_BIT,
                            (_porta&PINOUT.DI_A_BUTTON_1) == PINOUT.DI_A_BUTTON_1,
                            (_porta&PINOUT.DI_A_NSMBALERT) == PINOUT.DI_A_NSMBALERT,
                            (_porta&PINOUT.DI_A_SOCALERT) == PINOUT.DI_A_SOCALERT
                        )
                _is_button_pressed = ((_porta&PINOUT.DI_A_BUTTON_1) == PINOUT.DI_A_BUTTON_1) is False  # Active low
                _is_interrupt = False
                if (_wake_reason == 0x5) or (_wake_reason == 0x2):
                    if (_porta & PINOUT.DI_STARTUP_EVENT_INT) != 0x00:
                        _is_interrupt = True
            else:
                result = (0,0,0,0,1,1,1,0,0)
                _is_button_pressed = False
                _is_interrupt = False


            
            

            # BIT 0 -> DI_LEVEL
            # BIT 1 -> DI_RAIN
            # BIT 2 -> DI_DOOR
            # BIT 3 -> nSMBALERT
            # BIT 4 -> SOC_ALERT
            # BIT 5 -> BTN1
            # BIT 6 -> ACC_INT1
            # BIT 7 -> ACC_INT2

            door_is_open = result[2]

            if _porta is not None:
                _porta_str = "{porta:08b}".format(porta=_porta)
            else:
                _porta_str = "NotAvailable"
            _log.info("Wake={w}, DIA = {dia}, IsInterrupt = {i} - Port A = {porta_str} IMASK = {imask:08b} (door open = {do}, level low = {ll}, int = [{i1}, {i2}], button = {b}), elapsed since last OTA update: {e} [s], needs_to_check version is {n}".format(
                w=_wake_reason, dia = _dia_value, i=_is_interrupt, porta_str=_porta_str, imask=PINOUT.DI_STARTUP_EVENT_INT,
                do = door_is_open, ll=(result[3]), i1=result[4], i2=result[5],
                b=_is_button_pressed,
                e=_elapsed_s, n = _needs_to_check_update))

            

    except Exception as ex:
        _log.exc(ex, "Failed to check wakeup reason and dia status")
        _is_button_pressed = False

    return (_is_interrupt, _porta, _needs_to_check_update, _fs, _rtc, _is_button_pressed)