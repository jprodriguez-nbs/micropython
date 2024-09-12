
import machine

import uasyncio as asyncio
import logging
import colors
import ubinascii
import ntptime
import utime
import network


from async_SIM800L import AsyncModem
import wifimgr  as wifimgr

import planter_pinout as PINOUT
import planter.config as CFG
#import planter.display as PL_DISPLAY

_logger = logging.getLogger("NetworkMgr")
_logger.setLevel(logging.ERROR)

_config_dump_done = False
_is_running = False

class NetworkMgr(object):

    _modem = None
    _wlan = None
    _ppp = None

    _reference_ticks_ms = utime.ticks_ms()
    _wificonnected = False
    _pppconnected = False
    _wifi_connection_parameters = None
    _ppp_connection_parameters = None
    _apn = CFG.config()[CFG.K_GPRS][CFG.K_APN]
    _ppp_user = CFG.config()[CFG.K_GPRS][CFG.K_USER]
    _ppp_password = CFG.config()[CFG.K_GPRS][CFG.K_PSW]
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
    def set_debug_level(cls, l):
        _logger.setLevel(l)

    @classmethod
    def activate_ap(cls):
        wifimgr.activate_ap()

    @classmethod
    def stop(cls):
        cls._stop = True

    @classmethod
    async def hard_stop(cls):
        _logger.info("Disconnect WiFi and poweroff modem ...")
        if cls._wlan is not None:
            _logger.info("Disconnect from WLAN")
            # Disconnect from AP to release resources, so the frequent reconnections
            # do not make the ESP32 not able to connect to the AP
            cls._wlan.disconnect()
            # Deactivate wlan
            cls._wlan.active(False)

        if False:
            if cls._ppp is not None:
                _logger.info("Disconnect PPP")
                await cls.ppp_disconnect()
            elif cls._modem is not None:
                _logger.info("Disconnect GPRS")
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
        _logger.info("Poweroff modem")
        MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.OUT)
        MODEM_RST_PIN_OBJ = machine.Pin(PINOUT.MODEM_RST_PIN, machine.Pin.OUT)
        MODEM_POWER_ON_PIN_OBJ = machine.Pin(PINOUT.MODEM_POWER_ON_PIN, machine.Pin.OUT)

        MODEM_RST_PIN_OBJ.value(1)
        MODEM_PWKEY_PIN_OBJ.value(0)
        await asyncio.sleep_ms(1800)
        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        MODEM_PWKEY_PIN_OBJ.value(1)
        await asyncio.sleep_ms(500)
        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        MODEM_POWER_ON_PIN_OBJ.value(0)
        await asyncio.sleep_ms(500)
        if PINOUT.WDT_ENABLED:
            cls._wdt.feed()

        MODEM_RST_PIN_OBJ.value(0)

        # In version 20200327, output 4 is directly connected to PWRKEY in modem SIM800L
        # PWRKEY input is pulled up to VBAT inside the SIM800L
        # We have to pull down the PWRKEY to reset or to power off SIM800L
        # In order to ensure that SIM800L is power down while CPU is booting, we will leave
        # this pin as Pin.OUT and value 0 when goint to sleep
        MODEM_PWKEY_PIN_OBJ.value(0)
        
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
        return cls._wificonnected  or cls._pppconnected

    @classmethod
    def wifi_connected(cls):
        return cls._wificonnected
    
    @classmethod
    def ppp_connected(cls):
        return cls._pppconnected

    @classmethod
    def wifi_error(cls):
        return cls._wifi_error
    
    @classmethod
    def ppp_error(cls):
        return cls._ppp_error

    @classmethod
    def connection_screen(cls):
        screen_lines = None
        try:
            if cls._wificonnected:
                if cls._wifi_connection_parameters is not None and len(cls._wifi_connection_parameters)>=4:
                    screen_lines = [
                        "WiFi c {c}".format(c=cls._wificonnected),
                        "SSID {ssid}".format(ssid=cls._wifi_connection_parameters[0]),
                        "Channel {channel}".format(channel=cls._wifi_connection_parameters[2]),
                        "RSSI {RSSI}".format(RSSI=cls._wifi_connection_parameters[3]),
                        "{ts}".format(ts=cls.ts())
                    ]
                else:
                    screen_lines = [
                        "WiFi c {c}".format(c=False),
                        "SSID {ssid}".format(ssid="---"),
                        "Channel {channel}".format(channel="---"),
                        "RSSI {RSSI}".format(RSSI="---"),
                        "{ts}".format(ts=cls.ts())
                    ]

            elif cls._pppconnected:
                screen_lines = [
                    "PPP c {c}".format(c=cls._pppconnected),
                    "APN {apn}".format(apn=cls._apn or ""),
                    "IP {ip}".format(ip = cls._ppp_ip or ""),
                    "{ts}".format(ts=cls.ts())
                ]

        except Exception as ex:
            pass
        return screen_lines


    @classmethod
    async def setup_time(cls):
        bResult = False
        #
        # Set time
        #
        if cls.isconnected():
            ntptime.host = 'nz.pool.ntp.org'
            try:
                _logger.debug("NTP get time ... (Connected to WLAN = {c}, PPP = {c2})".format(c=cls._wificonnected, c2=cls._pppconnected))
                try:
                    if PINOUT.WDT_ENABLED:
                        cls._wdt.feed()

                    try:
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
                        _logger.debug ("Fecha/Hora (year, month, mday, week of year, hour, minute, second, milisecond): {ts_str}".format(ts_str=ts_str))
                    except Exception as ex:
                        _logger.exc(ex,"NTP error: {e}".format(e=str(ex)))

                except Exception as ex:
                    _logger.exc(ex,"NTP error: {e}".format(e=str(ex)))
                    bResult = False

 

                if PINOUT.WDT_ENABLED:
                    cls._wdt.feed()
                
                #cls.status.display_page = PlanterStatus.PAGE_WIFI
                #PL_DISPLAY.update_display_with_status(cls)
                

            except OSError as ex:
                _logger.exc(ex,"NTP failed - OSError: {e}".format(e=str(ex)))
                bResult = False

        return bResult


    @classmethod
    async def connect_wlan(cls):
        try:
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()

            _logger.debug("connect wlan ...")
            cls._wlan = await wifimgr.get_connection()
            if cls._wlan is not None:
                cls._wificonnected = cls._wlan.isconnected()
            
            connection_parameters = wifimgr.get_connection_parameters()
            cls._wifi_connection_parameters = connection_parameters
            if connection_parameters is not None:
                _logger.info("Interface's MAC: {mac}".format(mac=ubinascii.hexlify(network.WLAN().config('mac'),':').decode())) # print the interface's MAC
                _logger.info("Interface's IP/netmask/gw/DNS: {ip}\n".format(ip=cls._wlan.ifconfig())) # print the interface's IP/netmask/gw/DNS addresses

            if cls._wificonnected:
                cls._connection_event.set()

        except Exception as ex:
            _logger.exc(ex,"connect_wlan error: {e}".format(e=str(ex)))


    @classmethod
    def setup_modem(cls):
        try:
            _logger.debug('Create AsyncModem ...')

            # Create new modem object on the right Pins
            cls._modem = AsyncModem(modem_pwkey_pin    = PINOUT.MODEM_PWKEY_PIN,
                        modem_rst_pin      = PINOUT.MODEM_RST_PIN,
                        modem_power_on_pin = PINOUT.MODEM_POWER_ON_PIN,
                        modem_tx_pin       = PINOUT.MODEM_TX_PIN,
                        modem_rx_pin       = PINOUT.MODEM_RX_PIN)
        except Exception as ex:
            _logger.exc(ex,"AsyncModem create: {e}".format(e=str(ex)))

    @classmethod
    async def init_modem(cls):
        try:
            if cls._modem is None:
                return

            _logger.debug('AsyncModem initialize ...')
            # Initialize the modem
            await cls._modem.initialize()
        except Exception as ex:
            _logger.exc(ex,"AsyncModem init: {e}".format(e=str(ex)))

    @classmethod
    async def gprs_connect(cls):
        try:
            if cls._modem is None:
                cls.setup_modem()
                await cls.init_modem()

            # APN: movistar.es
            # CONFIG_MODEM_PPP_AUTH_USERNAME="movistar"
            # CONFIG_MODEM_PPP_AUTH_PASSWORD="movistar"

            # Connect the modem
            _logger.debug('{c}AsyncModem connect ...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
            await cls._modem.connect(apn=cls._apn, user=cls._ppp_user, pwd=cls._ppp_password)
            a = await cls._modem.get_ip_addr()
            _logger.info('{c}Modem IP address:{n} "{a}"'.format(a=str(a),c=colors.BOLD_GREEN,n=colors.NORMAL))

            v = await cls._modem.get_fwversion()
            _logger.info('{c}FW Version:{n} "{v}"'.format(v=str(v),c=colors.BOLD_GREEN,n=colors.NORMAL))
        except Exception as ex:
            _logger.exc(ex,"GPRS connect: {e}".format(e=str(ex)))

    @classmethod
    async def gprs_disconnect(cls):
        try:
            if cls._modem is None:
                return

            # Disconnect Modem
            _logger.debug('Disconnect Modem...')
            await cls._modem.disconnect()
        except Exception as ex:
            _logger.exc(ex,"GPRS disconnect: {e}".format(e=str(ex)))

    @classmethod
    async def gprs_get(cls, url):
        try:
            if cls._modem is None:
                return
            
            _logger.debug("{c}GPRS Get{n} '{url}'".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
            response = await cls._modem.http_request(url, 'GET')
            _logger.debug('Response status code: {c}'.format(c=response.status_code))
            _logger.debug('Response content: {c}'.format(c=response.content))
            return response
        except Exception as ex:
            _logger.exc(ex,"GPRS GET: {e}".format(e=str(ex)))


    @classmethod
    async def gprs_post(cls, url, json_data):
        try:
            if cls._modem is None:
                return

            _logger.debug("{c}GPRS POST{n} '{url}'".format(url=url, c=colors.BOLD_GREEN,n=colors.NORMAL))
            response = await cls._modem.http_request(url, 'POST', json_data, 'application/json')
            _logger.debug('Response status code: {c}'.format(c=response.status_code))
            _logger.debug('Response content: {c}'.format(c=response.content))
            return response
        except Exception as ex:
            _logger.exc(ex,"GPRS POST: {e}".format(e=str(ex)))

    @classmethod
    async def ppp_connect(cls):
        try:
            if cls._modem is None:
                cls.setup_modem()
                await cls.init_modem()

            # PPP communication
            _logger.debug('{c}Connect PPP...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
            cls._ppp = await cls._modem.ppp_connect(apn=cls._apn, user=cls._ppp_user, pwd=cls._ppp_password)
            if cls._ppp is not None:
                cls._pppconnected = cls._ppp.isconnected()
                if cls._pppconnected:
                    cls._ppp_connection_parameters = cls._ppp.ifconfig()
                    cls._ppp_ip = cls._ppp_connection_parameters[0]
                    _logger.info('{c}PPP connection established. IP = {ip} {n}'.format(ip=str(cls._ppp_ip), c=colors.BOLD_GREEN,n=colors.NORMAL))
                    cls._connection_event.set()

        except Exception as ex:
            _logger.exc(ex,"PPP: {e}".format(e=str(ex)))

    @classmethod
    async def ppp_disconnect(cls):
        try:
            if cls._ppp is None:
                return

            # Disconnect PPP
            _logger.debug('{c}nDisconnect PPP...{n}'.format(c=colors.BOLD_GREEN,n=colors.NORMAL))
            await cls._modem.ppp_disconnect()
        except Exception as ex:
            _logger.exc(ex,"PPP: {e}".format(e=str(ex)))


    @classmethod
    async def connection_task(cls):
        global _config_dump_done
        _logger.debug("Connection task started")
        exc_msg = None
        while (cls._stop is False):
            try:
                if cls.isconnected() is False:
                    if PINOUT.WIFI_ENABLED:
                         await cls.connect_wlan()
                         cls._wifi_error = cls._wificonnected is False
                    if cls.isconnected() is False:
                        can_ppp = CFG.can_ppp()
                        if can_ppp:
                            await cls.ppp_connect()
                            cls._ppp_error = cls._pppconnected is False
                        else:
                            _logger.debug("Cannot connect to PPP because there is no APN configured-> Skip")
                            if _config_dump_done is False:
                                _logger.debug("Config: {c}".format(c=str(CFG.config())))
                                _config_dump_done = True
            except Exception as ex:
                try:
                    new_msg = "connection_task: {e}".format(e=str(ex))
                    if new_msg != exc_msg:
                        _logger.exc(ex,"connection_task: {e}".format(e=str(ex)))
                        exc_msg = new_msg
                except:
                    pass

            await asyncio.sleep(2)
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()

        _logger.debug("Close connection and release resources")
        await cls.hard_stop()
        
        cls._stop_event.set()
        _logger.debug("Exit Connection task")
        cls._tasks.pop("connection", None)


    @classmethod
    async def setuptime_task(cls):
        _logger.debug("SetupTime task started")
        ts_now = utime.time()
        while (ts_now < 601432115) and (cls._stop is False):
            if cls.isconnected():
                ts_now = utime.time()
                if ts_now < 601432115:
                    # Time is not set
                    await cls.setup_time()
            await asyncio.sleep(2)
            if PINOUT.WDT_ENABLED:
                cls._wdt.feed()
        _logger.debug("Exit SetupTime task")
        cls._tasks.pop("setup_time", None)



    @classmethod
    async def nmtask(cls):
        global _is_running
        if _is_running is False:
            if "connection" not in cls._tasks:
                cls._tasks["connection"] = asyncio.create_task(cls.connection_task())
            if "setup_time" not in cls._tasks:
                cls._tasks["setup_time"] = asyncio.create_task(cls.setuptime_task())
            _is_running = True

    @classmethod
    def is_running(cls):
        global _is_running
        return _is_running