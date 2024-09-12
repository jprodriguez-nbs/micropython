import logging
import os
import utime
import ujson
import sys
import ure
import hashlib
import gc
import binascii

from micropython import const

import planter_pinout as PINOUT
import wifimgr as wifimgr

CONTROL_MODE_FLAG_PERIODIC        = const(0x01)
CONTROL_MODE_FLAG_SOIL_MOISTURE = const(0x02)
CONTROL_MODE_FLAG_CALENDAR      = const(0x04)
CONTROL_MODE_FLAG_FORCED        = const(0x08)
CONTROL_MODE_FLAG_DISABLED      = const(0x10)

K_ID = "id"
K_TZ = "tz"
K_WIFI = "wifi"
K_AP = "ap"
K_SSID = "ssid"
K_AGENT = "agent"
K_PROTOCOL = "protocol"
K_AGENT_INT = "agent_int"
K_AGENT_EXT = "agent_ext"
K_GPRS = "gprs"
K_APN = "apn"
K_USER = "user"
K_PSW = "psw"
K_LORA = "lora"
K_CODING = "coding"
K_NETWORK_ID = "network_id"
K_APPLICATION_ID = "application_id"
K_FEATURES = "features"
K_FEATURE_FLOW_METER = "flow_meter"
K_FEATURE_RAIN_SENSOR = "rain_sensor"
K_SOIL_MOISTURE = "soil_moisture"
K_ADDR = "addr"


K_TS = "ts"
K_MODE = "mode"
K_MOISTURE_LOW_TH = "moisture_low_th"
K_RAIN_TH_MMPH = "rain_threshold_mmph"
K_WAKENING_PERIOD = "wakening_period_s"
K_RAIN_MMPH = "rain_mmph"
K_CALENDAR = "calendar"
K_START = "start"
K_START_S = "start_s"
K_MAX_VOL_ML = "max_vol_ml"
K_MAX_DURATION_S = "max_duration_s"
K_PERIODIC = "periodic"
K_PUMP_PERIOD_S = "pump_period_s"
K_MOISTURE_SENSORS = "moisture_sensors"
K_TYPE = "type"
K_ADVANCED = "advanced"

# Minimum pump period in [s] when irrigation mode is SoilMoisture
K_ADV_SOIL_MOISTURE_BASED_PUMP_MIN_PERIOD_S = "sm_pump_min_period_s"

# Maximum time that the planter is going to sleep when the irrigation mode is SoilMoisture
K_ADV_SOIL_MOISTURE_CONTROL_MAX_SLEEP_S = "sm_mode_max_sleep_s"

# Maximum period of operation parameters retrieval from the server.
# This is used to calculate the maximum time to sleep
K_ADV_SERVER_GET_PARAMS_PERIOD_S = "svr_get_params_period_s"

# time shift from UTC to calculate local time, measured in hours
K_ADV_UTC_SHIFT = "utc_shift"

# Minimum battery level to enable pump. If the battery level is below this threshold, then we will not start irrigations
K_ADV_V_BATT_MIN_FOR_PUMP = "vbatt_min_for_pump"

# Minimum battery level to activate the LOW alarm
K_ADV_V_BATT_LOW = "vbatt_low"

# Minimum battery level to activate the DEAD alarm
K_ADV_V_BATT_DEAD = "vbatt_dead"

# Maximum time that the planter is going to sleep if the door is open
K_ADV_DOOR_OPEN_MAX_SLEEP_S = "door_open_max_sleep_s"

# Flow meter calibration: Liters per Hour @ the planter working flow point of operation.
# This parameter depends both on the flow meter and the construction of the planter and should be
# the liters per hour in normal operation when the pump is ON
K_ADV_WORK_FLOW_LPH ="work_flow_lph"

# Flow meter calibration: pulse frequency in [Hz] @ the planter working flow point of operation (i.e., for the work_flow_lph)
# This parameter depends both on the flow meter and the construction of the planter and should be
# the frequency of pulses that the flow meter will produce in normal operation when the pump is ON and flow is work_flow_lph
K_ADV_WORK_FLOW_PULSE_FREQ_HZ ="work_flow_pulse_freq_hz"

# Accelerometer motion theshlod, measured in [g], to produce an interrupt indicating impact
K_ADV_ACC_MOTION_THRESHOLD_G = "acc_motion_th_g"

# Rain probability threshold [%]. If the probability of rain is above this threshold, then irrigations will be skiped
K_ADV_RAIN_PROBABILITY_TH = "rain_prob_th"                          # Threshold

# Rain probability [%]. If the  current rain probability. If it is above the threshold, then irrigations will be skiped
K_ADV_RAIN_PROBABILITY = "rain_prob"                                # Current value

# Time threshold since the start of the irrigation to check for pulses and current protection
K_ADV_IRR_PROTECTION_TIME = "iprot_time"              

# Minimum number of pulses to determine if the irrigation should be aborted. If the measured pulses is below the threshold, then we stop the irrigation.
# If set to zero, then there is no protection and the irrigation will not stop even if we do not read pulses
K_ADV_IRR_PROTECTION_MINPULSES = "iprot_minpulses"    

# Enable the flow pulses filter by histeresys
K_ADV_FLOW_ENABLE_HYSTERESIS = "flow_en_hysteresis"

# GPRS

#_APN = "movistar.es"
#_PPP_USER = "movistar"
#_PPP_PSW = "movistar"


_CONFIG_FN = "config.json"
_PARAMS_FN = "params.json"


_CAL_DATA_START_S_POSITION = 0
_CAL_DATA_MAX_DURATION_POSITION = 1
_CAL_DATA_MAX_VOLUME_POSITION = 2
_CAL_DATA_MOISTURE_LOW_TH_POSITION = 3
_CAL_DATA_START_STR_POSITION = 4


# Static configuration
_config = {}
_config_sd = b''

# Operation parameters
_params = {}
_params_sd = b''

_logger = logging.getLogger("planter.config")
_logger.setLevel(logging.DEBUG)

def _default_config():
    return {
            K_ID: "J0001",
            K_TZ: "Europe/Madrid",
            K_WIFI: [
                "PS118_Guest1;1rbi.d3rmi$",
                "Jp-t;deb02ce9aed0#",
                "Totem;TOTEMTOTEM",
                "SantaCole_WPA;FEB100098C4322BBCDF111765A"
            ],
            K_AP: "ud-planter;urbidermis",
            K_AGENT_INT: "35.157.78.86:8080",
            K_AGENT_EXT: "35.157.78.86:8080",
            K_GPRS: {
                K_APN: "movistar.es",
                K_USER: "movistar",
                K_PSW: "movistar"
            },
            K_LORA: {
                K_CODING: "",
                K_NETWORK_ID: "",
                K_APPLICATION_ID: ""
            },
            K_FEATURES:
            {
                K_FEATURE_FLOW_METER: True,
                K_FEATURE_RAIN_SENSOR: False
            },
            K_SOIL_MOISTURE: [
                {
                    K_ID:"top",
                    K_TYPE: "jxbs-3001",
                    K_ADDR: "1",
                    K_MODE: ""
                },
                {
                    K_ID:"mid",
                    K_TYPE: "rs-ecth-n01-b",
                    K_ADDR: "2",
                    K_MODE: "main"
                }
            ]
        }


def _default_params():
    return {
                K_TS: 0,
                #K_MODE: CONTROL_MODE_FLAG_PERIODIC | CONTROL_MODE_FLAG_SOIL_MOISTURE,
                K_MODE: CONTROL_MODE_FLAG_PERIODIC,
                K_MOISTURE_LOW_TH: 15,
                K_RAIN_TH_MMPH: 0,
                K_RAIN_MMPH: 0,
                K_CALENDAR: [
                    {
                        K_START: "09:00",
                        K_MAX_VOL_ML: 4000.0,
                        K_MAX_DURATION_S: 50,
                        K_MOISTURE_LOW_TH: 23
                    },
                    {
                        K_START: "21:00",
                        K_MAX_VOL_ML: 4000.0,
                        K_MAX_DURATION_S: 50,
                        K_MOISTURE_LOW_TH: 23
                    }
                ],
                K_PERIODIC: {
                    K_PUMP_PERIOD_S: 288,
                    #K_PUMP_PERIOD_S: const(3600*24/2),
                    K_MAX_VOL_ML: 4000.0,
                    K_MAX_DURATION_S: 50
                },

                K_ADVANCED : {
                    K_ADV_SOIL_MOISTURE_BASED_PUMP_MIN_PERIOD_S : PINOUT.SOIL_MOISTURE_BASED_PUMP_MIN_PERIOD_S,
                    K_ADV_SERVER_GET_PARAMS_PERIOD_S : PINOUT.SERVER_GET_PARAMS_PERIOD_S,
                    K_ADV_SOIL_MOISTURE_CONTROL_MAX_SLEEP_S : PINOUT.SOIL_MOISTURE_CONTROL_MAX_SLEEP_S,
                    K_ADV_UTC_SHIFT : PINOUT.UTC_SHIFT,
                    K_ADV_V_BATT_MIN_FOR_PUMP : PINOUT.V_BATT_MIN_FOR_PUMP, 
                    K_ADV_V_BATT_LOW : PINOUT.V_BATT_LOW,
                    K_ADV_V_BATT_DEAD : PINOUT.V_BATT_DEAD,
                    K_ADV_DOOR_OPEN_MAX_SLEEP_S : PINOUT.DOOR_OPEN_MAX_SLEEP_S,
                    K_ADV_WORK_FLOW_LPH: PINOUT.WORK_FLOW_LPH,
                    K_ADV_WORK_FLOW_PULSE_FREQ_HZ: PINOUT.WORK_FLOW_PULSE_FREQ_HZ,
                    K_ADV_ACC_MOTION_THRESHOLD_G: PINOUT.DEFAULT_ACC_MOTION_TH,
                    K_ADV_RAIN_PROBABILITY_TH: 0,
                    K_ADV_RAIN_PROBABILITY: 0,
                    K_ADV_IRR_PROTECTION_TIME : 15,
                    K_ADV_IRR_PROTECTION_MINPULSES : 20,
                    K_ADV_FLOW_ENABLE_HYSTERESIS: True
                }
            }


def config():
    global _config
    return _config

def params():
    global _params
    return _params

def has_rain_sensor():
    global _config
    return _config[K_FEATURES][K_FEATURE_RAIN_SENSOR]

def has_sm_sensor():
    global _config
    r = K_SOIL_MOISTURE in _config and len(_config[K_SOIL_MOISTURE])>0
    return r

def has_flow_meter():
    global _config
    return _config[K_FEATURES][K_FEATURE_FLOW_METER]

def svr_get_params_period_s():
    global _params
    return _params[K_ADVANCED][K_ADV_SERVER_GET_PARAMS_PERIOD_S]


def can_ppp():
    if PINOUT.PPP_ENABLED and _config is not None:
        if K_GPRS in _config and K_APN in _config[K_GPRS]:
            _apn = _config[K_GPRS][K_APN]
        else:
            _apn = None
        if _apn is not None and len(_apn)>0:
            has_apn = True
        else:
            has_apn = False
    else:
        has_apn = False
    return has_apn


def planter_id():
    return _config[K_ID]

def _store_config(c_str):
    with open(_CONFIG_FN, "w") as f:
        f.write(c_str)

def _store_params(p_str):
    with open(_PARAMS_FN, "w") as f:
        f.write(p_str)

def update_wifi_config(c):
    if K_AP in c:
        ap_cfg = c[K_AP]
    else:
        ap_cfg = None
    if K_WIFI in c:
        wifi_dat = c[K_WIFI]
    else:
        wifi_dat = None
    wifimgr.update_wifi_cfg(ap_cfg,wifi_dat)

def set_config(c):
    global _config
    global _config_sd

    try:
        c_str = ujson.dumps(c)
        c_sd = hashlib.sha256(c_str).digest()
        if c_sd != _config_sd:
            # Config has changed. Update file
            _store_config(c_str)
            _config = c
            _config_sd = c_sd
            update_wifi_config(_config)
    except Exception as ex:
        _logger.exc(ex,"Failed to set config")
    gc.collect()

def calc_params_hash(p):
    if True:
        # Cannot calc hash of string generated by ujson.dumps because order is not consistent and hash changes
        l = ["'{k}':{v}".format(k=k, v=str(v)) for k,v in p.items()]
        l_str = ", ".join(sorted(l))
        sd = hashlib.sha256(l_str).digest()
        del l
        gc.collect()
        return (sd, l_str)
    else:
        p_str = ujson.dumps(p, sort_keys=True)
        sd = hashlib.sha256(p_str).digest()
        return (sd, p_str)

def set_params(p, from_store=False):
    global _params
    global _params_sd

    try:
        if from_store:
            # Read from store -> init current value before completing the parameters
            _params = p
            (_params_sd, l_str) = calc_params_hash(p)
            current_sd = _params_sd
        else:
            (aux, l_str) = calc_params_hash(_params)
            current_sd = aux

        # Add default params for missing keys
        dp = _default_params()
        for k,v in dp.items():
            if k not in p:
                p[k] = v

        p_str = ujson.dumps(p)
        (p_sd, l_str2) = calc_params_hash(p)
        #if (p_sd != current_sd):
        #if (l_str != l_str2):
        if (_params['ts'] != p['ts']):
            # params has changed. Update file
            # The stored parameters are used when there is no connectivity and params cannot be updated from the server
            _logger.debug("Previous params [hash: 0x{h}]: \n{s}".format(h=binascii.hexlify(current_sd), s=str(l_str)))
            _logger.debug("New params [hash: 0x{h}]: \n{s}".format(h=binascii.hexlify(p_sd), s=l_str2))
            _logger.debug("Params have changed -> update file.")
            _store_params(p_str)

        # Update params
        _params = p
        _params_sd = p_sd

    except Exception as ex:
        _logger.exc(ex,"Failed to set params")
    gc.collect()


def init():
    global _config
    global _config_sd
    global _params
    global _params_sd

    _logger.debug("Init - read config {fn}".format(fn=_CONFIG_FN))

    try:
        with open(_CONFIG_FN, "r") as f:
            _config = ujson.loads(f.read())
            update_wifi_config(_config)
    except Exception as ex:
        _logger.exc(ex,"Failed to read config from {fn} -> Create default and store".format(fn=_CONFIG_FN))
        _config = _default_config()
        _store_config(ujson.dumps(_config))

    _logger.debug("Calculate config SHA256 digest")
    _config_sd = hashlib.sha256(ujson.dumps(_config)).digest()

    _logger.debug("Init - read params {fn}".format(fn=_PARAMS_FN))
    try:
        with open(_PARAMS_FN, "r") as f:
            aux = ujson.loads(f.read())
            set_params(aux, from_store=True) # To add default keys if missing
    except Exception as ex:
        _logger.exc(ex,"Failed to read params from {fn} -> Create default and store".format(fn=_PARAMS_FN))
        _params = _default_params()
        _store_params(ujson.dumps(_params))

    _logger.debug("Calculate params SHA256 digest")
    _params_sd = hashlib.sha256(ujson.dumps(params())).digest()

    # Set planter id for traces
    logging.set_id(planter_id())

    _logger.debug("Init - GC collect")
    gc.collect()


#init()