

import gc
import micropython
import machine
import tools
print("NetworkMgr")
tools.free(True)


import uasyncio as asyncio
import logging
import colors
import ubinascii
import ntptime
import utime
import network
import gc
import arequests
import time

import umdc_pinout as PINOUT

if PINOUT.PING_ENABLED:
    import uping


#import wifimgr  as wifimgr

import umdc_config as CFG


from constants import *

_config_dump_done = False
_is_running = False

class NetworkMgr(object):

    _logger = logging.getLogger("NetworkMgr")
    _logger.setLevel(logging.DEBUG)

    _modem = None
    _wlan = None
    _ppp = None
    _iccid = None
    _rssi = None

    _reference_ticks_ms = utime.ticks_ms()
    _wificonnected = False
    _pppconnected = False
    _wifi_ip = None
    _ppp_ip = None
    _wifi_connection_parameters = None
    _ppp_connection_parameters = None
    __config = CFG.config()
    _apn = None
    _ppp_user = None
    _ppp_password = None
    
    
    try:    
        _apn = __config[CFG.K_GPRS][CFG.K_APN]
        _ppp_user = __config[CFG.K_GPRS][CFG.K_USER]
        _ppp_password = __config[CFG.K_GPRS][CFG.K_PSW]
    except Exception as ex:
        _logger.error("Failed to get PPP configuration from config: {e}".format(e=str(ex)))
        
    try:        
        if CFG.K_ICCID in  __config[CFG.K_GPRS]:
            _iccid = __config[CFG.K_GPRS][CFG.K_ICCID]
    except Exception as ex:
        _logger.error("Failed to get ICCID configuration from config: {e}".format(e=str(ex)))
          
    try:  
        if CFG.K_NTP in  __config:
            _ntp = __config[CFG.K_NTP]
        else:
            _ntp = "intxmdcotp02.sdg.abertistelecom.local"
    except Exception as ex:
        _logger.error("Failed to get NTP configuration from config: {e}".format(e=str(ex)))
            
    #_ntp = '10.1.152.102'
            

        
    _ppp_ip = None
    
    _rtc = machine.RTC()
    if PINOUT.WDT_ENABLED:
        _wdt = machine.WDT(timeout=PINOUT.WDT_TIMEOUT_MS)

    _connection_event = asyncio.Event()
    _time_setup_event = asyncio.Event()
    _core = None
    _tasks = {}
    _stop = False
    _stop_event = asyncio.Event()

    _wifi_error = False
    _ppp_error = False

    @classmethod
    def get_wifimgr():
        import wifimgr  as wifimgr
        gc.collect()
        return wifimgr


    @classmethod
    def set_debug_level(cls, l):
        cls._logger.setLevel(l)

    @classmethod
    def activate_ap(cls):
        cls.get_wifimgr().activate_ap()

    @classmethod
    def stop(cls):
        cls._stop = True

    @classmethod
    async def hard_stop(cls):
        cls._logger.info("Disconnect WiFi and poweroff modem ...")
        if cls._wlan is not None:
            cls._logger.info("Disconnect from WLAN")
            # Disconnect from AP to release resources, so the frequent reconnections
            # do not make the ESP32 not able to connect to the AP
            cls._wlan.disconnect()
            # Deactivate wlan
            cls._wlan.active(False)

        if False:
            if cls._ppp is not None:
                cls._logger.info("Disconnect PPP")
                await cls.ppp_disconnect()
            elif cls._modem is not None:
                cls._logger.info("Disconnect GPRS")
                await cls.gprs_disconnect()
        
        try:
            if cls._ppp is not None:
                del cls._ppp
                cls._ppp = None
        except:
            pass
        try:
            if cls._modem is not None:
                del cls._modem
                cls._modem = None
        except:
            pass



        # Power OFF GPRS Modem
        cls._logger.info("Poweroff modem")
        MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.OUT) if PINOUT.MODEM_PWKEY_PIN is not None else None
        MODEM_RST_PIN_OBJ = machine.Pin(PINOUT.MODEM_RST_PIN, machine.Pin.OUT) if PINOUT.MODEM_RST_PIN is not None else None
        MODEM_POWER_ON_PIN_OBJ = machine.Pin(PINOUT.MODEM_POWER_ON_PIN, machine.Pin.OUT) if PINOUT.MODEM_POWER_ON_PIN is not None else None

        if MODEM_RST_PIN_OBJ:
            cls._logger.info("MODEM RST pin {p} -> 1".format(p=PINOUT.MODEM_RST_PIN))
            MODEM_RST_PIN_OBJ.value(1)
            
        if MODEM_PWKEY_PIN_OBJ:
            cls._logger.info("MODEM PWKEY pin {p} -> {v}}".format(p=PINOUT.MODEM_PWKEY_PIN, v=PINOUT.MODEM_PWKEY_OFF))
            MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
            await asyncio.sleep_ms(1800)
        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        if MODEM_PWKEY_PIN_OBJ:
            cls._logger.info("MODEM PWKEY pin {p} -> {v}}".format(p=PINOUT.MODEM_PWKEY_PIN, v=PINOUT.MODEM_PWKEY_ON))
            MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_ON)
            await asyncio.sleep_ms(500)

        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        if MODEM_POWER_ON_PIN_OBJ:
            # Power off the modem
            cls._logger.info("MODEM POWER_ON pin {p} -> 0}".format(p=PINOUT.MODEM_POWER_ON_PIN))
            MODEM_POWER_ON_PIN_OBJ.value(0)
            await asyncio.sleep_ms(500)
            
        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        if MODEM_RST_PIN_OBJ:
            MODEM_RST_PIN_OBJ.value(0)

        # In version 20200327, output 4 is directly connected to PWRKEY in modem SIM800L
        # PWRKEY input is pulled up to VBAT inside the SIM800L
        # We have to pull down the PWRKEY to reset or to power off SIM800L
        # In order to ensure that SIM800L is power down while CPU is booting, we will leave
        # this pin as Pin.OUT and value 0 when goint to sleep
        if MODEM_PWKEY_PIN_OBJ:
            cls._logger.info("MODEM PWKEY pin {p} -> {v}}".format(p=PINOUT.MODEM_PWKEY_PIN, v=PINOUT.MODEM_PWKEY_OFF))
            MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
        
        #MODEM_RST_PIN_OBJ = machine.Pin(PINOUT.MODEM_RST_PIN, machine.Pin.IN, pull=None)
        #MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None)


    @classmethod
    def connection_event(cls):
        return cls._connection_event

    @classmethod
    def time_setup_event(cls):
        return cls._time_setup_event

    @classmethod
    def stop_event(cls):
        return cls._stop_event

    @classmethod
    def ts(cls):
        dt = cls._rtc.datetime()
        # (year, month, mday, week_of_year, hour, minute, second, milisecond)
        ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        return ts_str

    @classmethod
    def isconnected(cls):
        return cls.wifi_connected()  or cls.ppp_connected()

    @classmethod
    def wifi_connected(cls):
        if cls._wlan is not None:
            cls._wificonnected = cls._wlan.isconnected()
        return cls._wificonnected
    
    @classmethod
    def ppp_connected(cls):
        if cls._ppp is not None:
            cls._pppconnected = cls._ppp.isconnected()
        return cls._pppconnected

    @classmethod
    def wifi_ip(cls):
        if cls._wlan is not None:
            cls._wifi_ip = cls._wlan.ifconfig()
        return cls._wifi_ip
    
    @classmethod
    def ppp_ip(cls):
        if cls._ppp is not None:
            cls._ppp_ip = cls._ppp.ifconfig()
        return cls._ppp_ip


    @classmethod
    def connection_str(cls):
        
        _ppp_connected = cls.ppp_connected()
        _ppp_ip = cls.ppp_ip()
        
        _wifi_connected = cls.wifi_connected()
        _wifi_ip = cls.wifi_ip()
        
        ppp_str = _ppp_ip if _ppp_connected else "NO"
        wifi_str = _wifi_ip if _wifi_connected else "NO"
        
        result = "PPP {p}, WiFi {w}".format(p=ppp_str, w=wifi_str)
        return result

    @classmethod
    def iccid(cls):
        return cls._iccid

    @classmethod
    def rssi(cls):
        return cls._rssi

    @classmethod
    def wifi_error(cls):
        return cls._wifi_error
    
    @classmethod
    def ppp_error(cls):
        return cls._ppp_error

    @classmethod
    async def get_info_page(cls):

        try:
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()
            gc.collect()

            cls.set_debug_level(logging.DEBUG)
            
            if PINOUT.PING_ENABLED:                
                #server_hostname = 'intxmdcotp02.sdg.abertistelecom.local'
                server_hostname = PINOUT.PING_TARGET
                if server_hostname is not None and len(server_hostname):
                    try:
                        for i in range(PINOUT.NB_PING_LOOPS):
                            tools.free()
                            ping_target = server_hostname
                            #cls._logger.debug("Ping server: {hostname}".format(hostname=ping_target))
                            print("networkmgr - ping server: {hostname}".format(hostname=ping_target))
                            uping.ping(ping_target)
                    except Exception as ex:
                        cls._logger.error("get_info_page.ping({h}) error: {e}".format(h=ping_target, e=str(ex)))
                        
                else:
                    cls._logger.error("Server hostname is null or empty")
            
            if PINOUT.GET_INFO_PAGE_ENABLED:
                url = PINOUT.INFO_PAGE
                try:
                    #cls._logger.debug("Get info.php - URL: {url}".format(url=url))
                    print("Get info.php - URL: {url}".format(url=url))
                    response = await arequests.get(url, headers=GET_HEADERS)
                    cls._logger.debug("{c}Content{n}: {t}".format(c=colors.BOLD_GREEN,n=colors.NORMAL, t= await response.text()))
                except Exception as ex:
                    cls._logger.error("get_info_page({url}) error: {e}".format(url=url, e=str(ex)))
                    
                if PINOUT.WDT_ENABLED:
                    cls._wdt.feed()
            gc.collect()
            
        except Exception as ex:
            cls._logger.error("get_info_page error: {e}".format(e=str(ex)))


    @classmethod
    async def setup_time(cls):
        if PINOUT.NTP_TIME_ENABLED:
            bResult = False
            #
            # Set time
            #
            if cls.isconnected():
                #ntptime.host = 'nz.pool.ntp.org'
                #ntptime.host = '10.1.109.10'
                ntptime.host = cls._ntp
                
                try:
                    
                    try:
                        if PINOUT.WDT_ENABLED:
                            cls._wdt.feed()

                        #cls._logger.debug("Ping ntp server: {hostname}".format(hostname=cls._ntp))
                        #uping.ping(cls._ntp)
                        await cls.get_info_page()
                        
                        
                        if PINOUT.WDT_ENABLED:
                            cls._wdt.feed()

                        try:
                            #cls._logger.debug("NTP get time ... (Connected to WLAN = {c}, PPP = {c2}, ntp host={h})".format(c=cls._wificonnected, c2=cls._pppconnected,h=cls._ntp))
                            print("NTP get time ... (Connected to WLAN = {c}, PPP = {c2}, ntp host={h})".format(c=cls._wificonnected, c2=cls._pppconnected,h=cls._ntp))
                            ntptime.settime()
                            utc_shift_h = float(CFG.params()[CFG.K_ADVANCED][CFG.K_ADV_UTC_SHIFT])
                            utc_shift_s = int(utc_shift_h * 3600.0)
                            tm = utime.localtime(utime.mktime(utime.localtime()) + utc_shift_s)
                            tm = tm[0:3] + (0,) + tm[3:6] + (0,)
                            cls._rtc.datetime(tm)

                            # (year, month, mday, week_of_year, hour, minute, second, milisecond)=RTC().datetime()
                            # RTC().init((year, month, mday, week_of_year, hour+2, minute, second, milisecond)) # GMT correction. GMT+2
                            dt = cls._rtc.datetime()
                            ts_str = "{}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
                            cls._logger.debug ("Fecha/Hora (year, month, mday, week of year, hour, minute, second, milisecond): {ts_str}".format(ts_str=ts_str))
                        except Exception as ex:
                            cls._logger.exc(ex,"NTP error: {e}".format(e=str(ex)))

                    except Exception as ex:
                        cls._logger.exc(ex,"NTP error: {e}".format(e=str(ex)))
                        bResult = False

    

                    if PINOUT.WDT_ENABLED:
                        cls._wdt.feed()
                    
                    

                except OSError as ex:
                    cls._logger.exc(ex,"NTP failed - OSError: {e}".format(e=str(ex)))
                    bResult = False

        else:
            bResult = True

        return bResult


    @classmethod
    async def connect_wlan(cls):
        try:
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()

            cls._logger.debug("connect wlan ...")
            cls._wlan = await cls.get_wifimgr().get_connection()
            _ip = None
            if cls._wlan is not None:
                cls._wificonnected = cls._wlan.isconnected()
                _ip = cls._wlan.ifconfig()
            
                connection_parameters = cls.get_wifimgr().get_connection_parameters()
                cls._wifi_connection_parameters = connection_parameters
                if connection_parameters is not None:
                    cls._logger.info("Interface's MAC: {mac}".format(mac=ubinascii.hexlify(network.WLAN().config('mac'),':').decode())) # print the interface's MAC
                    cls._logger.info("Interface's IP/netmask/gw/DNS: {ip}\n".format(ip=_ip)) # print the interface's IP/netmask/gw/DNS addresses

                if cls._wificonnected:
                    cls._connection_event.set()

        except Exception as ex:
            cls._logger.exc(ex,"connect_wlan error: {e}".format(e=str(ex)))


    @classmethod
    def attachGSMtoPPP(cls, _uart):
        
        
        is_connected = False
        while is_connected is False:
            print("Create network.PPP")
            GPRS=network.PPP(_uart)
            time.sleep(1)
            print("Activate network.PPP")
            GPRS.active(True)
            time.sleep(1)
            print("Connect network.PPP with '{u}', '{p}'".format(u=PINOUT.PPP_USER, p=PINOUT.PPP_PSW))
            GPRS.connect(authmode=GPRS.AUTH_CHAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
            time.sleep(3)
            print("Check if network.PPP is connected")
            
            idx = 0
            last_msg = None
            while is_connected is False and idx < 100:            
                idx = idx + 1
                is_connected = GPRS.isconnected()
                _ip = GPRS.ifconfig()
                msg = "PPP connected {c}, IP {ip}".format(c=is_connected, ip=_ip)
                if msg != last_msg:
                    print(msg)
                    last_msg = msg
                else:
                    time.sleep(0.5)

            if is_connected is False:
                GPRS.active(False)
                time.sleep(1)
                del GPRS
                GPRS = None

        return GPRS

    @classmethod
    async def gprs_connect(cls):
        try:
            if cls._modem is None:
                from modem import Modem
                cls._modem = Modem(None)

            # Connect the modem
            cls._logger.debug('{c}Modem connect ...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
            (iccid, imei, rssi, revision, _uart) = cls._modem.connect(apn=cls._apn, user=cls._ppp_user, pwd=cls._ppp_password)
            if _uart is not None:
                del cls._modem
                del Modem
                cls._modem = None
                tools.free()
                _ppp = cls.attachGSMtoPPP(_uart)
                
                a = _ppp.ifconfig()
                cls._logger.info('{c}Modem IP address:{n} "{a}"'.format(a=str(a),c=colors.BOLD_GREEN,n=colors.NORMAL))
                # Free resources


            #v = await cls._modem.get_fwversion()
            #cls._logger.info('{c}FW Version:{n} "{v}"'.format(v=str(v),c=colors.BOLD_GREEN,n=colors.NORMAL))
        except Exception as ex:
            cls._logger.exc(ex,"GPRS connect: {e}".format(e=str(ex)))

    @classmethod
    async def gprs_disconnect(cls):
        try:
            if cls._modem is None:
                return

            # Disconnect Modem
            cls._logger.debug('Disconnect Modem...')
            cls._modem.disconnect()
        except Exception as ex:
            cls._logger.exc(ex,"GPRS disconnect: {e}".format(e=str(ex)))

    @classmethod
    async def gprs_get(cls, url):
        try:
            if cls._modem is None:
                return
            
            cls._logger.debug("{c}GPRS Get{n} '{url}'".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
            response = await cls._modem.http_request(url, 'GET')
            cls._logger.debug('Response status code: {c}'.format(c=response.status_code))
            cls._logger.debug('Response content: {c}'.format(c=response.content))
            return response
        except Exception as ex:
            cls._logger.exc(ex,"GPRS GET: {e}".format(e=str(ex)))


    @classmethod
    async def gprs_post(cls, url, json_data):
        try:
            if cls._modem is None:
                return

            cls._logger.debug("{c}GPRS POST{n} '{url}'".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
            response = await cls._modem.http_request(url, 'POST', json_data, 'application/json')
            cls._logger.debug('Response status code: {c}'.format(c=response.status_code))
            cls._logger.debug('Response content: {c}'.format(c=response.content))
            return response
        except Exception as ex:
            cls._logger.exc(ex,"GPRS POST: {e}".format(e=str(ex)))

    @classmethod
    async def ppp_connect(cls):
        try:
            import modem
            if cls._modem is None:
                cls._modem = modem.Modem(None)

            if cls._ppp is None or cls._ppp.isconnected() is False:
                # PPP communication
                cls._logger.debug('{c}Connect PPP...{n} ({ppp})'.format(c=colors.BOLD_GREEN,n=colors.NORMAL, ppp='None' if cls._ppp is None else  cls._ppp.isconnected()))
                
                if cls._ppp is not None:
                    # Clear
                    del cls._ppp
                    cls._ppp = None
                
                (cls._iccid, cls._imei, cls._rssi, cls._revision, _uart) = cls._modem.connect(apn=cls._apn, user=cls._ppp_user, pwd=cls._ppp_password)
                if _uart is not None:
                    del cls._modem
                    
                    cls._modem = None
                    tools.free()
                    cls._ppp =  cls.attachGSMtoPPP(_uart)
                    cls._pppconnected = cls._ppp.isconnected()
                    if cls._pppconnected:
                        cls._ppp_connection_parameters = cls._ppp.ifconfig()
                        cls._ppp_ip = cls._ppp_connection_parameters[0]
                        cls._logger.info('{c}PPP connection established. IP = {ip} {n}, ICCID={iccid}'.format(
                            ip=str(cls._ppp_ip), c=colors.BOLD_GREEN, n=colors.NORMAL, iccid=str(cls._iccid)))
                        cls._connection_event.set()
                if cls._iccid is not None:
                    if CFG.K_ICCID in cls.__config[CFG.K_GPRS]:
                        current_iccid = cls.__config[CFG.K_GPRS][CFG.K_ICCID]
                    else:
                        current_iccid = None
                    if cls._iccid != current_iccid:
                        cls.__config[CFG.K_GPRS][CFG.K_ICCID] = cls._iccid
                        # Update in flash
                        CFG.set_config(cls.__config)
                        
                await cls.get_info_page()
            del modem

        except Exception as ex:
            cls._logger.exc(ex,"PPP: {e}".format(e=str(ex)))

    @classmethod
    async def ppp_disconnect(cls):
        try:
            if cls._ppp is None:
                return

            # Disconnect PPP
            cls._logger.debug('{c}nDisconnect PPP...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
            await cls._modem.ppp_disconnect()
        except Exception as ex:
            cls._logger.exc(ex,"PPP: {e}".format(e=str(ex)))


    @classmethod
    async def connection_task(cls):
        global _config_dump_done
        cls._logger.debug("Connection task started")
        exc_msg = None
        while (cls._stop is False):
            try:
                if cls.isconnected() is False:
                    cls._logger.debug("connection_task - Is connected: PPP {ppp}, WiFi {wifi} -> {c}".format(
                        ppp='None' if cls._ppp is None else cls.ppp_connected(), 
                        wifi='None' if cls._wlan is None else cls.wifi_connected(), 
                        c=cls.isconnected()))
                    
                    if PINOUT.CONNECTION_PRIORITY[0] == 'ppp':
                        # Priority is PPP
                        can_ppp = CFG.can_ppp()
                        if can_ppp:
                            if cls.isconnected() is False:
                                await cls.ppp_connect()
                            cls._ppp_error = cls._pppconnected is False
                        else:
                            cls._logger.debug("Cannot connect to PPP because there is no APN configured-> Skip")
                            if _config_dump_done is False:
                                cls._logger.debug("Config: {c}".format(c=str(CFG.config())))
                                _config_dump_done = True
                        
                        # Backup is WiFi
                        if cls.isconnected() is False:            
                            if PINOUT.WIFI_ENABLED:
                                await cls.connect_wlan()
                                cls._wifi_error = cls._wificonnected is False
                    else:
                        # Priority is wifi
                        if PINOUT.WIFI_ENABLED:
                            if cls.isconnected() is False:
                                await cls.connect_wlan()
                            cls._wifi_error = cls._wificonnected is False
                        if cls.isconnected() is False: 
                            # Backup is PPP
                            can_ppp = CFG.can_ppp()
                            if can_ppp:
                                await cls.ppp_connect()
                                cls._ppp_error = cls._pppconnected is False
                            else:
                                cls._logger.debug("Cannot connect to PPP because there is no APN configured-> Skip")
                                if _config_dump_done is False:
                                    cls._logger.debug("Config: {c}".format(c=str(CFG.config())))
                                    _config_dump_done = True       
                                             
            except Exception as ex:
                try:
                    new_msg = "connection_task: {e}".format(e=str(ex))
                    if new_msg != exc_msg:
                        cls._logger.exc(ex,"connection_task: {e}".format(e=str(ex)))
                        exc_msg = new_msg
                except:
                    pass

            await asyncio.sleep(2)
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()

        cls._logger.debug("connection_task STOP -> Close connection and release resources")
        try:
            await asyncio.wait_for(cls.hard_stop(), timeout = 5)
        except asyncio.TimeoutError:
            pass
        
        cls._stop_event.set()
        cls._logger.debug("Exit Connection task")
        cls._tasks.pop("connection", None)


    @classmethod
    async def setuptime_task(cls):
        if PINOUT.NTP_TIME_ENABLED:
            cls._logger.debug("SetupTime task started")
            ts_now = utime.time()
            idx = 0
            while (ts_now < 601432115) and (cls._stop is False) and (idx < 10):
                if cls.isconnected():
                    ts_now = utime.time()
                    if ts_now < 601432115:
                        # Time is not set
                        await cls.setup_time()
                await asyncio.sleep(2)
                if PINOUT.WDT_ENABLED:
                    cls._wdt.feed()
                idx = idx + 1
            cls._logger.debug("Exit SetupTime task")
        cls._tasks.pop("setup_time", None)

    @classmethod
    async def nmtask(cls):
        print ("NeworkMgr task created")     
        global _is_running
        if _is_running is False:
            if "connection" not in cls._tasks:
                cls._tasks["connection"] = asyncio.create_task(cls.connection_task())
            if PINOUT.NTP_TIME_ENABLED:
                if "setup_time" not in cls._tasks:
                    cls._tasks["setup_time"] = asyncio.create_task(cls.setuptime_task())
            _is_running = True

    @classmethod
    def is_running(cls):
        global _is_running
        return _is_running
    