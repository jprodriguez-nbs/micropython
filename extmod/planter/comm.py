
from networkmgr import NetworkMgr
import uasyncio as asyncio


import ujson
import arequests
#import app.frozen.arequests as arequests
import gc
import logging
import planter_pinout as PINOUT
import utime
import machine
import colors
import planter.config as CFG
import uping
import json

import power_monitor as power_monitor

#from time_it import asynctimeit, timed_function


_planter = None
_ts_last_params = 0
_ts_last_status_post = 0
_ts_last_get_params_trial = 0


_get_headers = {"Connection": "close"}
_post_headers = {
    'content-type': 'application/json',
    "Connection": "close"
    }

"""
_get_headers = {}
_post_headers = {
    'content-type': 'application/json'
    }
"""

_logger = logging.getLogger("planter.comm")
_logger.setLevel(logging.DEBUG)
_get_params_lock = asyncio.Lock()
_post_lock = asyncio.Lock()
_rtc = machine.RTC()

_post_data = ""

_enabled = True

def trace_error(ex, msg):
    if NetworkMgr.is_running:
        ns = "RUNNING"
    else:
        ns = "STOP"
    if CFG.can_ppp():
        if NetworkMgr.ppp_connected():
            ppp = "CONNECTED"
        else:
            ppp = "NOT CONNECTED"
    else:
        ppp = "DISABLED"
    if NetworkMgr.wifi_connected():
        w = "CONNECTED"
    else:
        w = "NOT CONNECTED"
    _logger.exc(ex, "{msg} (networkmgr {ns}, WiFi {w}, PPP {ppp}): {e}".format(msg=msg, e=str(ex), ns=ns, ppp=ppp, w=w), nopost=True)


async def _ensure_connection(cls):
    if not _enabled: return
    result = NetworkMgr.isconnected()
    return result


async def get_config(cls):
    if not _enabled: return

    connected = await _ensure_connection(cls)

    if connected:
        cls.status.update_url()
        url = cls.status.config_url
        
        _logger.debug("GetConfig - URL: {url}".format(url=url))
        response = await arequests.get(url, headers=_get_headers)
        _logger.debug("{c}Config{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
        new_static_config = await response.json()
        cls.status.static_config = new_static_config["data"]


async def get_downlink_messages(cls):
    if not _enabled: 
        return
    if cls.status.downlink_messages is not None and len(cls.status.downlink_messages)>0: 
        # Already retrieved
        return

    connected = await _ensure_connection(cls)

    if connected:
        cls.status.update_url()
        url = cls.status.messages_url
        
        _logger.debug("Get Downlink Messages - URL: {url}".format(url=url))
        response = await arequests.get(url, headers=_get_headers)
        li_messages = []
        try:
            #_logger.debug("{c}Downlink Messages{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            r = await response.json()
            if r is not None:
                li_messages = json.loads(r)
                for msg in li_messages:
                    _logger.debug("{c}Downlink message{n} {m}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, m=msg))
        except Exception as ex:
            _logger.exc(ex, "{c}Downlink Messages{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
        
        
        for m in li_messages:
            if m not in cls.status.downlink_messages:
                cls.status.downlink_messages.append(m)


async def get_params(cls):
    if not _enabled: return

    global _ts_last_params
    global _ts_last_get_params_trial
    try:
        connected = await _ensure_connection(cls)

        if connected:
            cls.status.update_url()
            # Limit get_params frequency for the case when the agent is not available
            ts_now = utime.time()
            elapsed_s = ts_now - _ts_last_get_params_trial
            if elapsed_s > PINOUT.SERVER_GET_PARAMS_RETRY_PERIOD_S:
                # Enough time has passed -> try to get params
                _ts_last_get_params_trial = ts_now

                old_utc_shift_h = float(CFG.params()[CFG.K_ADVANCED][CFG.K_ADV_UTC_SHIFT])
                url = cls.status.params_url
                
                server_hostname = cls.status.server_hostname
                if server_hostname is not None and len(server_hostname):
                    _logger.debug("Ping server: {hostname}".format(hostname=server_hostname))
                    uping.ping(server_hostname)
                else:
                    _logger.error("Server hostname is null or empty")
                
                _logger.debug("GetParams - URL: {url}".format(url=url))
                response = await arequests.get(url, headers=_get_headers)
                _logger.debug("{c}Params{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
                new_params = await response.json()
                cls.status.params = new_params
                _ts_last_params = ts_now

                new_utc_shift_h = float(CFG.params()[CFG.K_ADVANCED][CFG.K_ADV_UTC_SHIFT])
                if old_utc_shift_h != new_utc_shift_h:
                    # Need to update time
                    _logger.debug("UTC Shift changed from {o} to {n} -> need to update time".format(o=old_utc_shift_h, n=new_utc_shift_h))
                    await NetworkMgr.setup_time()

        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Get Params error")
        


async def _post_status(cls):
    if not _enabled: return

    global _post_data
    try:
        connected = await _ensure_connection(cls)

        if connected:
            url = cls.status.status_url
            _post_data = ujson.dumps([cls.status.status]).encode('UTF8')
            l = len(_post_data)
            _logger.debug("\n{c}PostStatus{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            #await asyncio.sleep_ms(100)
            response = await arequests.post(url, headers=_post_headers, data=_post_data)
            _logger.debug("{c}Post status answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            response_obj = await response.json()
            if (("result" in response_obj) and (response_obj["result"] is True)) or \
               (("status" in response_obj) and (response_obj["status"] == "Accepted")):
                # The irrigation cycles have been received by the agent, therefore we can clear the list
                #cls.status.clear_irrigation_cycles()
                #cls.status.clear_power_measures()
                pass
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Post status error")
        


async def _post_irrigation(cls):
    if not _enabled: return

    global _post_data
    try:
        data = cls.status.irrigation_cycles()
        nb_cycles = len(data)
        if nb_cycles> 0:
            connected = await _ensure_connection(cls)

            if connected:
                url = cls.status.irrigation_url
                li_cycles = []
                for c in data:
                    try:
                        li_cycles.append(c.to_dict())
                    except Exception as ex:
                        _logger.exc(ex, "PostIrrigation error: {e} - Data: {d}".format(e=str(ex), d=str(c)))
                _post_data = ujson.dumps(li_cycles).encode('UTF8')
                l = len(_post_data)
                _logger.debug("\n{c}PostIrrigation{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()
                response = await arequests.post(url, headers=_post_headers, data=_post_data)
                _logger.debug("{c}PostIrrigation answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()
                response_obj = await response.json()
                result_ok = (("result" in response_obj) and (response_obj["result"] is True)) or \
                            (("status" in response_obj) and (response_obj["status"] == "Accepted"))

                if result_ok:
                    # The irrigation cycles have been received by the agent, therefore we can clear the list
                    cls.status.clear_irrigation_cycles(True)
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "PostIrrigation error")
        


async def _post_rain(cls):
    if not _enabled: return

    global _post_data
    try:
        data = cls.status.rain_measures()
        nb_cycles = len(data)
        if nb_cycles> 0:
            connected = await _ensure_connection(cls)

            if connected:
                url = cls.status.rain_url
                li_measures = []
                for c in data:
                    try:
                        li_measures.append(c.to_dict())
                    except Exception as ex:
                        _logger.exc(ex, "Post rain error: {e} - Data: {d}".format(e=str(ex), d=str(c)))
                _post_data = ujson.dumps(li_measures).encode('UTF8')
                l = len(_post_data)
                _logger.debug("\n{c}PostRain{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()
                response = await arequests.post(url, headers=_post_headers, data=_post_data)
                t= await response.text()
                _logger.debug("{c}Post rain answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= t))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()

                result_ok = False
                if (response is not None) and len(t)>0 :
                    try:
                        response_obj = await response.json()
                        result_ok = (("result" in response_obj) and (response_obj["result"] is True)) or \
                                    (("status" in response_obj) and (response_obj["status"] == "Accepted"))
                    except:
                        result_ok = False

                if result_ok:
                    # The rain measures have been received by the agent, therefore we can clear the list
                    cls.status.clear_rain_measures(True)
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Post rain error")


async def _post_power(cls):
    if not _enabled: return

    global _post_data
    try:
        has_pm_measures = power_monitor.has_measures()
        if has_pm_measures:
            data = cls.status.power_measures
            if data is not None:
                connected = await _ensure_connection(cls)

                if connected:
                    url = cls.status.power_url
                    pm_data = data.to_dict()
                    _post_data = ujson.dumps(pm_data).encode('UTF8')
                    l = len(_post_data)
                    _logger.debug("\n{c}PostPower{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
                    if PINOUT.WDT_ENABLED:
                        cls.wdt.feed()
                    response = await arequests.post(url, headers=_post_headers, data=_post_data)
                    _logger.debug("{c}Post power answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
                    if PINOUT.WDT_ENABLED:
                        cls.wdt.feed()
                    response_obj = await response.json()
                    if (("result" in response_obj) and (response_obj["result"] is True)) or \
                    (("status" in response_obj) and (response_obj["status"] == "Accepted")):
                        # The power measures have been received by the agent, therefore we can clear the list
                        cls.status.clear_power_measures()
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Post power error")


async def _post_traces(cls):
    if not _enabled: return

    global _post_data
    try:
        li_traces = logging.get_traces()
        nb_traces = len(li_traces)
        if nb_traces > 0:
            connected = await _ensure_connection(cls)

            if connected:
                url = cls.status.traces_url
                _post_data = ujson.dumps(logging.get_traces()).encode('UTF8')
                l = len(_post_data)
                _logger.debug("\n{c}PostTraces{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()
                #await asyncio.sleep_ms(100)
                response = await arequests.post(url, headers=_post_headers, data=_post_data)
                _logger.debug("{c}Post traces answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
                if PINOUT.WDT_ENABLED:
                    cls.wdt.feed()
                response_obj = await response.json()
                if (("result" in response_obj) and (response_obj["result"] is True)) or \
                (("status" in response_obj) and (response_obj["status"] == "Accepted")):
                    # The traces have been received by the agent, therefore we can clear the list
                    logging.clear_traces()
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Post traces error")
        # Clear the traces if we failed to send them, to avoid having a snow-ball
        logging.clear_traces()


async def _post_events(cls):
    if not _enabled: return

    global _post_data
    try:
        connected = await _ensure_connection(cls)

        if connected:
            url = cls.status.events_url
            _post_data = ujson.dumps(cls.status.events()).encode('UTF8')
            l = len(_post_data)
            _logger.debug("\n{c}PostEvents{n} - URL: {url} - Data: {l} bytes\n{post_data}\n".format(c=colors.BOLD_GREEN,n=colors.NORMAL, url=url, l=l, post_data = _post_data))
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            #await asyncio.sleep_ms(100)
            response = await arequests.post(url, headers=_post_headers, data=_post_data)
            _logger.debug("{c}Post events answer{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
            if PINOUT.WDT_ENABLED:
                cls.wdt.feed()
            response_obj = await response.json()
            if (("result" in response_obj) and (response_obj["result"] is True)) or \
               (("status" in response_obj) and (response_obj["status"] == "Accepted")):
                # The events have been received by the agent, therefore we can clear the list
                cls.status.clear_events()
            cls.status.clear_events()
        if PINOUT.WDT_ENABLED:
            cls.wdt.feed()
        gc.collect()
    except Exception as ex:
        trace_error(ex, "Post events error")


# https://github.com/peterhinch/micropython-async/blob/master/v3/docs/TUTORIAL.md#31-lock
async def post_status_and_events(cls, force_post):
    if not _enabled: return

    global _ts_last_status_post
    await _post_lock.acquire()

    try:
        ts_now = utime.time()
        elapsed_s = ts_now - _ts_last_status_post
        if (elapsed_s > PINOUT.MIN_POST_PERIOD_S) or force_post:
            connected = await _ensure_connection(cls)

            if connected:

                cls.status.update_url()
                if force_post:
                    _logger.debug("post_status_and_events forced ...")
                await _post_irrigation(cls)
                if cls.status.has_rain_sensor:
                    await _post_rain(cls)
                await _post_power(cls)
                await _post_status(cls)
                await _post_events(cls)
                await _post_traces(cls)
                _ts_last_status_post = ts_now
    except Exception as ex:
        trace_error(ex, "post_status_and_events error")


    _post_lock.release()


async def post_events(cls):
    if not _enabled: return

    global _ts_last_status_post
    await _post_lock.acquire()

    try:
        connected = await _ensure_connection(cls)

        if connected:
            cls.status.update_url()
            await _post_events(cls)
            await _post_traces(cls)
    except Exception as ex:
        trace_error(ex, "post_events error")

    _post_lock.release()

async def do_get_params(cls):
    if not _enabled: return

    got_params = False
    await _get_params_lock.acquire()

    try:
        dt = _rtc.datetime()
        year = dt[0]
        bNeedsNetwork = (year < 2020)
        has_to_get_params = cls.status.has_to_get_params() or bNeedsNetwork

        connected = await _ensure_connection(cls)

        if connected:
            # Get params
            if has_to_get_params:
                cls.status.update_url()
                await get_params(cls)
                await get_downlink_messages(cls)
                
                got_params = True
    except Exception as ex:
        trace_error(ex, "do_get_params error")

    _get_params_lock.release()
    return got_params




def init(planter):
    global _planter
    _planter = planter
    pass

def disable():
    global _enabled
    _enabled = False