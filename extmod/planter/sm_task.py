import logging
import machine
import uasyncio as asyncio

from uModBus.async_serial import AsyncSerial
import soil_moisture as SM

from planter.status import *
import planter_pinout as PINOUT



_modbus_obj = None
_sm_sensors = {}
_sm_main_sensor = None

ts_last_sm_read_schedule = 0

flag_read_sm = False

_logger = logging.getLogger("SM_TASK")
_logger.setLevel(logging.DEBUG)

def is_modbus_defined():
    return _modbus_obj is not None

def init_sm_sensor(cls):
    global _modbus_obj
    global _sm_sensors
    global _sm_main_sensor

    uart_id = PINOUT.RS485_UART
    if _modbus_obj is None:
        msg = "Init modbus at (UART={id}, TX={tx}, RX={rx})".format(id=uart_id, tx=PINOUT.RS485_TXD, rx=PINOUT.RS485_RXD)
        _logger.info(msg)
        _modbus_obj = AsyncSerial(uart_id, tx_pin=PINOUT.RS485_TXD, rx_pin=PINOUT.RS485_RXD,
                                baudrate=PINOUT.RS485_BAUDRATE, data_bits=PINOUT.RS485_DATABITS,
                                stop_bits=PINOUT.RS485_STOPBIT, parity=PINOUT.RS485_PARITY)

        _modbus_obj.debug = False
        _modbus_obj.read_async = True

    try:
        _logger.debug("Build soil moisture sensors. Config:\n{c}\n".format(c=str(cls.status.static_config[CFG.K_SOIL_MOISTURE])))
    except Exception as ex:
        _logger.exc(ex,"Failed to print soil moisture sensors config: {e}".format(e=ex))

    full_sm_config = cls.status.static_config[CFG.K_SOIL_MOISTURE]
    if full_sm_config is None or len(full_sm_config)==0:
        _logger.debug("SoilMoisture sensor configuration is empty -> will not read soilmoisture")
    else:
        for sm_config in full_sm_config:
            try:
                sm_id = sm_config[CFG.K_ID]
                sm_obj = SM.SoilMoistureSensor(modbus=_modbus_obj, name=sm_id, 
                                            model=sm_config[CFG.K_TYPE], slave_addr=int(sm_config[CFG.K_ADDR]))
                _sm_sensors[sm_obj.name] = sm_obj
                if "main" in sm_config[CFG.K_MODE]:
                    _sm_main_sensor = sm_id
                    _logger.debug("Main soil moisture sensor is {n}".format(n=sm_id))
            except Exception as ex:
                _logger.exc(ex,"Failed to build soil moisture sensor driver for sensor {n}: {e}".format(n=str(sm_config), e=str(ex)))

def release_sm_sensor():
    global _modbus_obj
    global _sm_sensors
    global _sm_main_sensor
    if _sm_sensors is not None:
        for n, sms in _sm_sensors.items():
            del sms
        _sm_sensors.clear()
        _sm_sensors = {}

    if _modbus_obj is not None:
        del _modbus_obj
        _modbus_obj = None

async def do_read_sm(cls, args):
    global _sm_sensors
    global _sm_main_sensor

    _dl = logging.INFO
    # Read soil moisture
    try:  
        """
        power_3v_on = cls.status.load_3v_on
        power_5v_on = cls.status.load_5v_on
        power_12v_on = cls.status.load_12v_on

        if (power_12v_on is False) or (power_3v_on is False) or (power_5v_on is False):
            _logger.debug("Read soil moisture - TURN POWER ON")
            await cls.enable_power(True)
            # Wait some time so the sensor can power up and start measuring
            await asyncio.sleep(PINOUT.SOIL_MOISTURE_POWERUP_GUARD_S)
        """
        
        if _modbus_obj is None:
            # Resources have been released -> do not read
            return
        
        has_changed = await cls.enable_power(True)
        if has_changed:
            _logger.debug("Read soil moisture - TURN POWER ON")
            await asyncio.sleep(PINOUT.SOIL_MOISTURE_POWERUP_GUARD_S)

        # Read soil moisture
        if len(_sm_sensors):
            for n, sms in _sm_sensors.items():
                try:
                    if _dl <= logging.DEBUG:
                        _logger.debug("Read SM sensor {n}".format(n=n))
                    r = await sms.read()
                    if r is not None:
                        [smd, read_succeeded] = r
                        if read_succeeded and smd is not None:
                            if n == _sm_main_sensor:
                                # Update status
                                if _dl <= logging.DEBUG:
                                    _logger.debug("Update SM status with sensor '{n}' read data: VWC {vwc}, Temp {t}".format(n=n, vwc=smd.vwc, t=smd.temp))
                                cls.status.soil_moisture_vwc = smd.vwc
                                cls.status.soil_temperature_c = smd.temp
                                cls.status.soil_moisture_data_available = True
                                cls.status.soil_moisture_read_trial = 0
                            else:
                                if _dl <= logging.DEBUG:
                                    _logger.debug("Discard SM data of sensor '{n}': VWC {vwc}, Temp {t}".format(n=n, vwc=smd.vwc, t=smd.temp))
                        else:
                            if _dl <= logging.DEBUG:
                                result_str = "succeeded" if read_succeeded else "failed"
                                if smd is None:
                                    smd_str = "None"
                                else:
                                    smd_str = "VWC {vwc}, Temp {t}".format(vwc=smd.vwc, t=smd.temp)
                                _logger.warning("Read SM sensor '{n}' -> Read {f}, smd {smd}".format(n=n, f=result_str, smd = smd_str))
                            if n == _sm_main_sensor:
                                cls.status.soil_moisture_read_trial += 1
                    else:
                        if _dl <= logging.DEBUG:
                            _logger.warning("Read SM sensor '{n}' -> Result is NONE".format(n=n))
                        if n == _sm_main_sensor:
                            cls.status.soil_moisture_read_trial += 1
                except Exception as ex:
                    msg = "do_read_sm failed to read sensor '{n}'. Error: {e}".format(n=n, e=str(ex))
                    _logger.exc(ex,msg)


    except Exception as ex:
        _logger.exc(ex,"do_read_sm error: {e}".format(e=str(ex)))



async def soil_moisture_task(cls):
    _logger.debug("Soil Moisture TASK started. {n} sensors defined".format(n=len(_sm_sensors)))
    await asyncio.sleep(PINOUT.SM_READ_PERIOD_S)
    while True:
        try:
            #await cls.enable_power(True)
            await do_read_sm(cls, None)
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
        except Exception as ex:
            _logger.exc(ex,"Failed to read soil moisture: {e}".format(e=ex))
        await asyncio.sleep(PINOUT.SM_READ_PERIOD_S)



async def search_sm(cls):
    await cls.init()
    await cls.enable_power(True)
    cls.cycle_counter = PINOUT.SOIL_MOISTURE_POWERUP_GUARD_S + 1
    if PINOUT.WDT_ENABLED:
        cls.wdt = machine.WDT(timeout=PINOUT.WDT_TIMEOUT_MS)
    init_sm_sensor(cls)
    for n in _sm_sensors:
        _sm_sensors[n].search()


async def sm_scan(cls, args):
    await cls.init()
    await cls.enable_power(True)
    cls.cycle_counter = PINOUT.SOIL_MOISTURE_POWERUP_GUARD_S + 1
    if PINOUT.WDT_ENABLED:
        cls.wdt = machine.WDT(timeout=PINOUT.WDT_TIMEOUT_MS)
    init_sm_sensor(cls)
    if _sm_sensors is None or len(_sm_sensors)<1:
        _logger.error("sm_sensors is empty, cannot scan")
    for n in _sm_sensors:
        _logger.debug("Scan sensor {n}".format(n=n))
        _sm_sensors[n].scan()