
from micropython import const

import ina3221
import uasyncio
import utime
import logging
import machine

import time

import struct
import nsClassWriter

import ina226
import axp202.axp202 as axp202
from nsPlanterPowerData import Power3ChData, Power1ChData
from nsPlanterPowerTimeSeries import PowerTimeSeries

POWER_MONITOR_MODEL_INA3221 = const(0)
POWER_MONITOR_MODEL_INA219 = const(1)
POWER_MONITOR_MODEL_INA226 = const(2)
POWER_MONITOR_MODEL_INA233 = const(3)


POWER_BUS_FORMAT = "{v:>6.3f}| {i:>8.3f}"

MEASURES_FN = 'measures.dat'
HISTORIZATION_PERIOD_S = const(300)

BUFFER_SIZE_SAMPLES = 3000

SLEEP_BETWEEN_I2C_OPERATIONS = False

_INA3221_CONFIG_MASK = ina3221.C_AVERAGING_MASK | ina3221.C_VBUS_CONV_TIME_MASK | ina3221.C_SHUNT_CONV_TIME_MASK | ina3221.C_MODE_MASK
_INA3221_CONFIG_VALUE = ina3221.C_AVERAGING_256_SAMPLES | ina3221.C_VBUS_CONV_TIME_332US | ina3221.C_SHUNT_CONV_TIME_332US | ina3221.C_MODE_SHUNT_AND_BUS_CONTINOUS

_power_buses = {"pv": {"v": 0.0, "i": 0.0},
                "batt":  {"v": 0.0, "i": 0.0},
                "pump":  {"v": 0.0, "i": 0.0},
                "5v":  {"v": 0.0, "i": 0.0},
                "485":  {"v": 0.0, "i": 0.0},
                "flow":  {"v": 0.0, "i": 0.0},
                "level":  {"v": 0.0, "i": 0.0},
                "CPU":  {"v": 0.0, "i": 0.0}
                }
_power_monitors = {
    "12v": {
        "pmtype": POWER_MONITOR_MODEL_INA3221,
        "ch": ["pv", "batt", "pump"],
        "addr": 0x40,
        "available": False,
        "drv": None,
        #"data": bytearray(b"\0" * (BUFFER_SIZE_SAMPLES*Power3ChData.packlength)),
        #"idx": 0,
        "data": [],
        "sample_size": Power3ChData.packlength,
        "type": Power3ChData
    }
}

def add_pm_5v():
    global _power_monitors
    _power_monitors["5v"] = {
        "pmtype": POWER_MONITOR_MODEL_INA3221,
        "ch": ["485","flow","level"],
        "addr": 0x41,
        "available": False,
        "drv": None,
        #"data": bytearray(b"\0" * (BUFFER_SIZE_SAMPLES*Power3ChData.packlength)),
        #"idx": 0,
        "data": [],
        "sample_size": Power3ChData.packlength,
        "type": Power3ChData
    }

def add_pm_12v_b():
    global _power_monitors
    _power_monitors["12v_b"] = {
        "pmtype": POWER_MONITOR_MODEL_INA226,
        "ch": ["CPU"],
        "addr": 0x45,
        "available": False,
        "drv": None,
        #"data": bytearray(b"\0" * (BUFFER_SIZE_SAMPLES*Power1ChData.packlength)),
        #"idx": 0,
        "data": [],
        "sample_size": Power1ChData.packlength,
        "type": Power1ChData
    }


_i2c = None
_rtc = machine.RTC()
_full_debug = False

_logger = logging.getLogger("PM")
_logger.setLevel(logging.DEBUG)
_axp202 = None

_sw = nsClassWriter.StructWriter()

# Reference tick_ms
_reference_tick_ms = utime.ticks_ms()


_ts_last_power_historization_ms = None
_ts_last_batt_check = 0

def get_axp202():
    global _axp202
    return _axp202

def has_pm(name):
    return name in _power_monitors

def add_power_data(pm_cfg, pd):
    #p = _sw.write(pd)
    #ss = pm_cfg["sample_size"]
    #idx = pm_cfg["idx"]
    #pm_cfg["data"][idx*ss : (idx+1)*ss] = p
    #pm_cfg["idx"] = (idx + 1) % BUFFER_SIZE_SAMPLES
    pm_cfg["data"].append(pd)
    while len(pm_cfg["data"]) > BUFFER_SIZE_SAMPLES:
        pm_cfg["data"].pop(0)



def _ina3221_init(ina3221_dev):
    if ina3221.INA3221.IS_FULL_API:
        # print("full API sample: improve accuracy")
        # improve accuracy by slower conversion and higher averaging
        # each conversion now takes 128*0.008 = 1.024 sec
        # which means 2 seconds per channel
        ina3221_dev.update(reg=ina3221.C_REG_CONFIG,
                    mask=_INA3221_CONFIG_MASK,
                    value=_INA3221_CONFIG_VALUE)

    # enable all 3 channels. You can comment (#) a line to disable one
    name = ina3221_dev.name
    ch = ina3221_dev.channel_names
    if ch[0] is not None:
        ina3221_dev.enable_channel(1)
    if ch[1] is not None:        
        ina3221_dev.enable_channel(2)
    if ch[2] is not None:        
        ina3221_dev.enable_channel(3)
    if _full_debug:
        s = ina3221_dev.current_config()
        print("{n} Config -> {s}".format(n=name, s=s))


def _ina226_init(ina226_dev):
    ina226_dev.set_calibration()

def init(i2c, buses = None):
    global _i2c
    global _power_monitors
    global _logger
    global _axp202

    _i2c = i2c

    # Scan to find which monitors are installed
    i2c_devices = i2c.scan()

    pm_keys = list(_power_monitors.keys())
    _logger.debug("Init power_monitor. I2C devices: {d}. Defined power_monitors = {l}. Enabled buses: {b}".format(
        d=str(i2c_devices), l=pm_keys, b=buses))

    try:
        for pm_name, pm_cfg in _power_monitors.items():
            _logger.debug("Process power_monitor {n}".format(n=pm_name))
            try:
                if (buses is not None) and (pm_name not in buses):
                    _logger.warning("Discard power_monitor {pm_name} because it is not enabled".format(pm_name=pm_name))
                    continue
                pm_a = pm_cfg["addr"]
                pm_t = pm_cfg["pmtype"]
                if pm_t == POWER_MONITOR_MODEL_INA3221:
                    model = "INA3221"
                elif pm_t == POWER_MONITOR_MODEL_INA226:
                    model = "INA226"
                else:
                    _logger.error("Unknown power_monitor type {t}".format(pm_t))
                    model = ""

                if pm_a in i2c_devices:
                    pm_cfg["available"] = True
                    if pm_t == POWER_MONITOR_MODEL_INA3221:
                        msg = "Create INA3221 {n} at addr {a} ...".format(n=pm_name, a=pm_a)
                        _logger.debug(msg)
                        d = ina3221.INA3221(_i2c, pm_a, name=pm_name, channel_names = pm_cfg["ch"])
                        _ina3221_init(d)
                        pm_cfg["drv"] = d

                    elif pm_t == POWER_MONITOR_MODEL_INA226:
                        msg = "Create INA226 {n} at addr {a} ...".format(n=pm_name, a=pm_a)
                        _logger.debug(msg)
                        d = ina226.INA226(_i2c, pm_a, name=pm_name, channel_name = pm_cfg["ch"][0])
                        _ina226_init(d)
                        pm_cfg["drv"] = d
                    else:
                        _logger.error("Unknown power_monitor type {t}".format(pm_t))
        
                else:
                    msg = "Failed to find {m} {n} at addr {a} - Found devices are: {d}".format(m=model, n=pm_name, a=pm_a, d=str(i2c_devices))
                    _logger.error(msg)
            except Exception as ex:
                _logger.exc(ex, 'Failed to initialise power_monitor {n} @ {a}'.format(n=pm_name, a=pm_a))

    except Exception as ex:
        _logger.exc(ex, 'Failed to initialise power_monitors')

    try:
        if 52 in i2c_devices:
            _logger.debug("Create AXP192 PMU device")
            _axp202 = axp202.PMU(i2c, intr=35, address=52)
            _axp202.setChgLEDMode(axp202.AXP20X_LED_OFF)
            #_axp202.setChgLEDMode(axp202.AXP20X_LED_LOW_LEVEL)
            _axp202.enableCharging()

            _axp202.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_VOL_ADC1)
            _axp202.enableADC(axp202.AXP202_ADC1, axp202.AXP202_VBUS_CUR_ADC1)
            _axp202.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_VOL_ADC1)
            _axp202.enableADC(axp202.AXP202_ADC1, axp202.AXP202_BATT_CUR_ADC1)
        else:
            msg = "Failed to find PMU AXP192 at addr {a} - Found devices are: {d}".format(m="AXP192", a=52, d=str(i2c_devices))
            _logger.error(msg)
    except Exception as ex:
        _logger.exc(ex, 'Failed to initialise power_monitor {n} @ {a}'.format(n="AXP192", a=52))

async def _cycle_ina3221(pm_name, pm_cfg, bShow):
    ina3221_dev = pm_cfg["drv"]

    if ina3221_dev is None:
        if "none_communicated" not in pm_cfg:
            msg = "Cannot cycle INA3221 {n} at addr {a} - Device is None".format(n=pm_name, a=pm_cfg["addr"])
            _logger.error(msg)
            pm_cfg["none_communicated"] = True # Do not communicate again the error
        return None

    if ina3221.INA3221.IS_FULL_API: # is_ready available only in "full" variant
        if not ina3221_dev.is_ready:
            if bShow:
                _logger.debug ("INA3221 {name} not ready, still measuring".format(name=pm_name))
            return None

    if bShow:
        print("------------------------------")
        line_title =         "Measurement   "
        line_psu_voltage =   "PSU voltage   "
        line_load_voltage =  "Load voltage  "
        line_shunt_voltage = "Shunt voltage "
        line_current =       "Current       "

        #line_title_short =         "M   "
        #line_psu_voltage_short =   "V+  "
        #line_load_voltage_short =  "V-  "
        #line_shunt_voltage_short = "S mV"
        #line_current_short =       "I mA"

    l=[None, None, None, None, None]
    d=[None, (0,0), (0,0), (0,0)]
    l[0] = "{n:<3} V |   I [mA]".format(n=ina3221_dev.name)

    n=[None, "","",""]
    channel_names = ina3221_dev.channel_names
    if channel_names and len(channel_names)>=3:
        n[1] = channel_names[0]
        n[2] = channel_names[1]
        n[3] = channel_names[2]

    for chan in range(1,4):
        if ina3221_dev.is_channel_enabled(chan):
            bus_voltage = ina3221_dev.bus_voltage(chan)
            if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
            shunt_voltage = ina3221_dev.shunt_voltage(chan)
            if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
            current = ina3221_dev.current(chan)
            if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        else:
            bus_voltage = 0
            shunt_voltage = 0
            current = 0

        if bShow:
            line_title +=         "| {c:d}- {n:<8} ".format(c=chan,n=n[chan])
            line_psu_voltage +=   "| {:6.3f}    V ".format(bus_voltage + shunt_voltage)
            line_load_voltage +=  "| {:6.3f}    V ".format(bus_voltage)
            line_shunt_voltage += "| {:9.6f} V ".format(shunt_voltage)
            line_current +=       "| {:9.6f} A ".format(current)

            #line_title_short +=         "| C{:d} ".format(chan)
            #line_psu_voltage_short +=   "|{:2.2f}".format(bus_voltage + shunt_voltage)
            #line_load_voltage_short +=  "|{:2.2f}".format(bus_voltage)
            #line_shunt_voltage_short += "|{:2.2f}".format(shunt_voltage*1000)
            #line_current_short +=       "|{:2.2f}".format(current*1000)

        v = bus_voltage + shunt_voltage

        #
        # HACK FOR PUMP
        #
        if pm_name == '12v' and chan==3:
            # Calculate pump power
            # We are measuring the negative return wire of the pump
            # The voltage accross the pump is the difference between the 
            # battery voltage and the measured pump negative wire voltage
            # When the pump is off, the measured voltage is equal to the battery, 12V
            # When the pump is on, the negative wire is connected to GND and 
            # the measured voltage in the pump negative wire is approx 0V
            vbatt = d[2][0]
            v = vbatt - v

        p = v * current

        l[chan] = "{v:>6.3f}| {i:>8.3f}".format(v=v, i=current*1000)
        d[chan]=(v, current, p)
        if n[chan] in _power_buses:
            pb = _power_buses[n[chan]]
            pb["v"] = v
            pb["i"] = current

    ticks_ms = utime.ticks_ms()

    pd = Power3ChData(ticks_ms, d[1][0], d[1][1], d[2][0], d[2][1], d[3][0], d[3][1])
    add_power_data(pm_cfg, pd)


    if bShow:
        print(line_title)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_psu_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_load_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_shunt_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_current)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)

    return (l,d)

async def _cycle_ina226(pm_name, pm_cfg, bShow):
    ina226_dev = pm_cfg["drv"]

    if ina226_dev is None:
        if "none_communicated" not in pm_cfg:
            msg = "Cannot cycle INA226 {n} at addr {a} - Device is None".format(n=pm_name, a=pm_cfg["addr"])
            _logger.error(msg)
            pm_cfg["none_communicated"] = True # Do not communicate again the error
        return None

    if bShow:
        print("------------------------------")
        line_title =         "Measurement   "
        line_psu_voltage =   "PSU voltage   "
        line_load_voltage =  "Load voltage  "
        line_shunt_voltage = "Shunt voltage "
        line_current =       "Current       "

        #line_title_short =         "M   "
        #line_psu_voltage_short =   "V+  "
        #line_load_voltage_short =  "V-  "
        #line_shunt_voltage_short = "S mV"
        #line_current_short =       "I mA"

    l=[None, None, None, None, None]
    d=[None, (0,0), (0,0), (0,0)]
    l[0] = "{n:<3} V |   I [mA]".format(n=ina226_dev.name)

    n=[None, "","",""]
    channel_name = ina226_dev.channel_name
    if channel_name:
        n[1] = channel_name


    chan = 1
    bus_voltage = ina226_dev.bus_voltage
    if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
    shunt_voltage = ina226_dev.shunt_voltage
    if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
    current = ina226_dev.current
    if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)


    if bShow:
        line_title +=         "| {c:d}- {n:<8} ".format(c=chan,n=n[chan])
        line_psu_voltage +=   "| {:6.3f}    V ".format(bus_voltage + shunt_voltage)
        line_load_voltage +=  "| {:6.3f}    V ".format(bus_voltage)
        line_shunt_voltage += "| {:9.6f} V ".format(shunt_voltage)
        line_current +=       "| {:9.6f} A ".format(current)

        #line_title_short +=         "| C{:d} ".format(chan)
        #line_psu_voltage_short +=   "|{:2.2f}".format(bus_voltage + shunt_voltage)
        #line_load_voltage_short +=  "|{:2.2f}".format(bus_voltage)
        #line_shunt_voltage_short += "|{:2.2f}".format(shunt_voltage*1000)
        #line_current_short +=       "|{:2.2f}".format(current*1000)

        v = bus_voltage + shunt_voltage
        p = v * current
        l[chan] = "{v:>6.3f}| {i:>8.3f}".format(v=bus_voltage + shunt_voltage, i=current*1000)
        d[chan]=(v, current, p)
        if n[chan] in _power_buses:
            pb = _power_buses[n[chan]]
            pb["v"] = v
            pb["i"] = current

    ticks_ms = utime.ticks_ms()
    pd = Power1ChData(ticks_ms, d[1][0], d[1][1])
    add_power_data(pm_cfg, pd)

    if bShow:
        print(line_title)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_psu_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_load_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_shunt_voltage)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
        print(line_current)
        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)

    return (l,d)

def _append_measure (m_str):
    return
    try:
        with open(MEASURES_FN, "a") as f:
            f.write(m_str)
            f.write("\n")
    except Exception as ex:
        _logger.exc(ex, 'Failed to append measure to {fn}'.format(fn=MEASURES_FN))


def _historize(current_ts_ms):
    try:
        global _power_buses
        global _ts_last_power_historization_ms
        # 15 minutes
        #ePV_mWh = _power_buses["pv"]["acc"]
        #eBatt_mWh = _power_buses["batt"]["acc"]
        #e12_mWh = _power_buses["12v"]["acc"]

        ePV_mWh = accumulated_power("12v", "pv", _ts_last_power_historization_ms, current_ts_ms)
        eBatt_mWh = accumulated_power("12v", "batt", _ts_last_power_historization_ms, current_ts_ms)
        e12_mWh = accumulated_power("12v", "12v", _ts_last_power_historization_ms, current_ts_ms)

        dt = _rtc.datetime()
        ts_str = "{}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        trace_str = "{ts};{ePV};{eBatt};{e12}".format(ts=ts_str, ePV=ePV_mWh, eBatt=eBatt_mWh, e12=e12_mWh)
        _logger.debug("Energy register: {t} mWh".format(t=trace_str))

        _ts_last_power_historization_ms = current_ts_ms
        _append_measure(trace_str)
    except Exception as ex:
        _logger.exc(ex, '_historize')


async def cycle(bShow):
    global _power_monitors
    global _power_buses
    global _ts_last_power_historization_ms
    global _ts_last_batt_check

    try:
        if _axp202 is not None:
            ts_now = utime.time()
            if ts_now-_ts_last_batt_check > 15:
                _ts_last_batt_check = ts_now
                isCharging = _axp202.isCharging()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
                chargingEnabled = _axp202.isChargingEnable()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
                busV = _axp202.getVbusVoltage()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
                busC = _axp202.getVbusCurrent()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
                battV = _axp202.getBattVoltage()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)
                battC = _axp202.getBattChargeCurrent()
                if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(1)

                if chargingEnabled:
                    if isCharging:
                        chStr = "ENABLED, CHARGING"
                    else:
                        chStr = "ENABLED, NOT CHARGING"
                else:
                    chStr = "DISABLED"

                if bShow:
                    #battPct = _axp202.getBattPercentage()
                    #_logger.debug("AXP192: isCharging: V: %f C:%f  BC:%f  perce:%d" % (voltage, current, battCurrent,perce))
                    msg = "AXP192: Charging {e}: BUS: V: {busV} C:{busC} ; BATT: V: {battV} C:{battC}".format(
                        e = chStr,
                        busV=busV, busC = busC, battV=battV, battC = battC
                    )
                    _logger.debug(msg)
    except Exception as ex:
        _logger.exc(ex, 'Failed to cycle PMU AXP192')

    if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(10)
    #time.sleep(0.1)
    

    for pm_name, pm_cfg in _power_monitors.items():
        try:
            if bShow:
                _logger.debug("Cycle powermonitor {name}".format(name=pm_name))
            if pm_cfg["available"] is False:
                continue
            pm_t = pm_cfg["pmtype"]
            if pm_t == POWER_MONITOR_MODEL_INA3221:
                m = await _cycle_ina3221(pm_name, pm_cfg, bShow)
                if m is not None:
                    pm_cfg["m"] = m


            if pm_t == POWER_MONITOR_MODEL_INA226:
                m = await _cycle_ina226(pm_name, pm_cfg, bShow)
                if m is not None:
                    pm_cfg["m"] = m
            current_ts_ms = utime.ticks_ms()
            if _ts_last_power_historization_ms is not None:
                elapsed_ms = utime.ticks_diff(current_ts_ms, _ts_last_power_historization_ms)
                elapsed_s = elapsed_ms / 1000
                if elapsed_s >= HISTORIZATION_PERIOD_S:
                    _historize(current_ts_ms)

        except Exception as ex:
            _logger.exc(ex, 'Failed to cycle power monitor {m}'.format(m=pm_name))

        if SLEEP_BETWEEN_I2C_OPERATIONS: await uasyncio.sleep_ms(10)
        #time.sleep(0.1)

    try:
        if "5v" in _power_monitors:
            _power_buses["5v"] =  { "v": (_power_buses["485"]["v"]+ _power_buses["flow"]["v"]+_power_buses["level"]["v"])/3,
                                    "i": (_power_buses["485"]["i"]+ _power_buses["flow"]["i"]+_power_buses["level"]["i"])}
    except:
        pass

    return _power_buses

def to_tuple():
    global _power_buses
    r = (
        _power_buses["pv"]["v"], _power_buses["pv"]["i"],
        _power_buses["batt"]["v"], _power_buses["batt"]["i"],
        _power_buses["12v"]["v"], _power_buses["12v"]["i"],
        _power_buses["485"]["v"], _power_buses["485"]["i"]+ _power_buses["flow"]["i"]+_power_buses["level"]["i"]
    )
    return r

def to_display(name):
    global _power_monitors
    if name in _power_monitors:
        if "m" in _power_monitors[name]:
            return _power_monitors[name]["m"][0]
        else:
            return None
    return None

def to_dict():
    global _power_buses
    r = {}
    #for n in ["pv", "batt", "12v", "5v"]:
    for n in ["pv", "batt", "12v"]:
        if n in _power_buses:
            pb = _power_buses[n]
            r[n] = {
                "v": pb["v"], "i": pb["i"]
            }
    return r

def to_bin():
    global _power_monitors
    data = _power_monitors['12v']['data']
    r=''
    if len(data):
        last_data = data[-1]
        r = last_data.to_bin()
    return r
    

def power_measures():
    reference_ms = utime.ticks_ms()
    reference_ts = utime.time()
    pts = PowerTimeSeries(reference_ms, reference_ts)
    for name in _power_monitors:
        pm = _power_monitors[name]
        pts.add_serie(name, pm["type"], pm["ch"])
        if len(pm["data"]):
            pts.add_list(name, pm["data"])
    return pts

def has_measures():
    r = False
    for name in _power_monitors:
        pm = _power_monitors[name]
        if len(pm["data"]):
            r = True
    return r

def clear_power_measures():
    for name in _power_monitors:
        _power_monitors[name]["data"].clear()


def accumulated_power(name, ch, start_ms, end_ms):

    acc_ws = 0.0

    if name in _power_monitors:
        pm = _power_monitors[name]
        try:
            idx = pm["ch"].index(ch)
            n = idx + 1
        except Exception as ex:
            _logger.exc(ex, 'channel {ch} does not exist in powermonitor {name}'.format(ch=ch, name=name))
            return None
        
        d = pm["data"]
        previous_item = None
        for item in d:
            item_ms = item.ticks_ms
            start_offset_ms = utime.ticks_diff(item_ms, start_ms)
            end_offset_ms = utime.ticks_diff(end_ms, item_ms)
            if start_offset_ms > 0 and end_offset_ms>0:
                if previous_item is not None:
                    duration_s = float(utime.ticks_diff(item_ms, previous_item.ticks_ms))/1000.0
                    (v,i) = previous_item.get_ch(n)
                    power_w = v*i
                    power_ws = power_w * duration_s
                    acc_ws = acc_ws + power_ws
            previous_item = item
        
    acc_mwh = int((acc_ws / 3600.0) * 1000)

    return acc_mwh
        