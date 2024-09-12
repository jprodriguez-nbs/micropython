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

import umdc_pinout as PINOUT
import wifimgr as wifimgr

from constants import *


# GPRS

_CONFIG_FN = "config.json"
_PARAMS_FN = "params.json"


# Static configuration
_config = {}
_config_sd = b''

# Operation parameters
_params = {}
_params_sd = b''

_logger = logging.getLogger("umdc.config")
_logger.setLevel(logging.DEBUG)

# intxmdcotp02.sdg.abertistelecom.local

def _default_config():
    return {
            K_ID: "J0001",
            K_TZ: "Europe/Madrid",
            K_WIFI: [
                "PS118_Guest1;1rbi.d3rmi$",
                "Jp-t;deb02ce9aed0#"
            ],
            K_AP: "ud-umdc",
            K_PROTOCOL: "https",
            K_AGENT_INT: "intxmdcotp02.sdg.abertistelecom.local:8282",
            K_AGENT_EXT: "intxmdcotp02.sdg.abertistelecom.local:8282",
            K_MQTT_BROKER_PORT: "8883",
            K_NTP: "intxmdcotp02.sdg.abertistelecom.local",
            K_GPRS: {
                K_APN: "clnxpt.vf.global",
                K_USER: "Portugal",
                K_PSW: "1234RTU",
                K_ICCID:"0"
            }
        }


def _default_params():
    return {
                
                K_ADVANCED : {
                    K_ADV_UTC_SHIFT : PINOUT.UTC_SHIFT
                }
            }


def config():
    global _config
    if K_ID not in _config:
        init()
    return _config

def params():
    global _params
    return _params


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


def umdc_id():
    if K_ID not in _config:
        init()
    return _config[K_ID] if K_ID in _config else 0

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

    # Set umdc id for traces
    logging.set_id(umdc_id())

    _logger.debug("Init - GC collect")
    gc.collect()


#init()