# Imports

USE_ASYNC = False

import gc
import micropython
import machine
import tools
print("Async SIM800L USE_ASYNC={a}".format(a=USE_ASYNC))
print (tools.free(True))



import time
import json
from app.umdc_pinout import WDT_ENABLED
import utime
import socket

import logging as logging
import uasyncio as asyncio
import timetools
import network
import hwversion

import sys
from test.raw_ppp import raw_ppp as raw_ppp


gc.collect()

SLEEP_MS = 100

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

WDT_ENABLED = hwversion.WDT_ENABLED
if WDT_ENABLED:
    _wdt = machine.WDT(timeout=240000)

ALLOW_SSL = True
DETAILED_DEBUG = True



# Commands dictionary. Not the best approach ever, but works nicely.
commands = {
    # General commands
    '+++':  {'string': '+++', 'timeout': 3, 'end': 'OK'},
    'modeminfo':  {'string': 'ATI', 'timeout': 3, 'end': 'OK'},
    'fwrevision': {'string': 'AT+CGMR', 'timeout': 3, 'end': 'OK'},
    'battery':    {'string': 'AT+CBC', 'timeout': 3, 'end': 'OK'},
    'scan':       {'string': 'AT+COPS=?', 'timeout': 60, 'end': 'OK'},
    'network':    {'string': 'AT+COPS?', 'timeout': 3, 'end': 'OK'},
    'signal':     {'string': 'AT+CSQ', 'timeout': 3, 'end': 'OK'},
    'checkreg':   {'string': 'AT+CREG?', 'timeout': 3, 'end': 'OK'},
    'setapn':     {'string': 'AT+SAPBR=3,1,"APN","@@DATA@@"', 'timeout': 3, 'end': 'OK'},
    'setuser':    {'string': 'AT+SAPBR=3,1,"USER","@@DATA@@"', 'timeout': 3, 'end': 'OK'},
    'setpwd':     {'string': 'AT+SAPBR=3,1,"PWD","@@DATA@@"', 'timeout': 3, 'end': 'OK'}, # Appeared on hologram net here or below
    'initgprs':   {'string': 'AT+SAPBR=3,1,"Contype","GPRS"', 'timeout': 3, 'end': 'OK'},
    'opengprs':   {'string': 'AT+SAPBR=1,1', 'timeout': 3, 'end': 'OK'},
    'getbear':    {'string': 'AT+SAPBR=2,1', 'timeout': 3, 'end': 'OK'},
    'inithttp':   {'string': 'AT+HTTPINIT', 'timeout': 3, 'end': 'OK'},
    'sethttp':    {'string': 'AT+HTTPPARA="CID",1', 'timeout': 3, 'end': 'OK'},
    'checkssl':   {'string': 'AT+CIPSSL=?', 'timeout': 3, 'end': 'OK'},
    'enablessl':  {'string': 'AT+HTTPSSL=1', 'timeout': 3, 'end': 'OK'},
    'disablessl': {'string': 'AT+HTTPSSL=0', 'timeout': 3, 'end': 'OK'},
    'initurl':    {'string': 'AT+HTTPPARA="URL","@@DATA@@"', 'timeout': 3, 'end': 'OK'},
    'doget':      {'string': 'AT+HTTPACTION=0', 'timeout': 6, 'end': '+HTTPACTION'},
    'setcontent': {'string': 'AT+HTTPPARA="CONTENT","@@DATA@@"', 'timeout': 3, 'end': 'OK'}, # "data" is data_lenght in this context, while 5000 is the timeout
    'postlen':    {'string': 'AT+HTTPDATA=@@DATA@@,5000', 'timeout': 3, 'end': 'DOWNLOAD'},
    'dumpdata':   {'string': '@@DATA@@', 'timeout': 1, 'end': 'OK'},
    'dopost':     {'string': 'AT+HTTPACTION=1', 'timeout': 6, 'end': '+HTTPACTION'},
    'getdata':    {'string': 'AT+HTTPREAD', 'timeout': 3, 'end': 'OK'},
    'closehttp':  {'string': 'AT+HTTPTERM', 'timeout': 3, 'end': 'OK'},
    'closebear':  {'string': 'AT+SAPBR=0,1', 'timeout': 3, 'end': 'OK'},
    
    # PPPoS commands
    'syncbaud':    {'string': 'AT', 'timeout': 1, 'end': 'OK'},
    'reset':       {'string': 'ATZ', 'timeout': 3, 'end': 'OK'},
    'disconnect':  {'string': 'ATH', 'timeout': 20, 'end': 'OK'},   # Use "NO CARRIER" here?
    #'checkpin':    {'string': 'AT+CPIN?', 'timeout': 3, 'end': '+CPIN: READY'},
    'checkpin':    {'string': 'AT+CPIN?', 'timeout': 3, 'end': 'OK'},
    'nosms':       {'string': 'AT+CNMI=0,0,0,0,0', 'timeout': 3, 'end': 'OK'},
    'ppp_setapn':  {'string': 'AT+CGDCONT=1,"IP","@@DATA@@"', 'timeout': 3, 'end': 'OK'},
    'getipdetails':  {'string': 'AT+CGDCONT?', 'timeout': 3, 'end': 'OK'},
    'ppp_connect': {'string': 'AT+CGDATA="PPP",1', 'timeout': 3, 'end': 'CONNECT'},
    'ppp_dial':     {'string': 'ATD*99***1#', 'timeout': 3, 'end': 'CONNECT'},
    'rfon':        {'string': 'AT+CFUN=1', 'timeout': 3, 'end': 'OK'},
    'rfoff':       {'string': 'AT+CFUN=4', 'timeout': 3, 'end': 'OK'},
    'echoon':      {'string': 'ATE1', 'timeout': 3, 'end': 'OK'},
    'echooff':     {'string': 'ATE0', 'timeout': 3, 'end': 'OK'},

    'creg0':       {'string': 'AT+CREG0', 'timeout': 3, 'end': 'OK'},
    'cgreg0':       {'string': 'AT+CREG0', 'timeout': 3, 'end': 'OK'},
    'qicsgp':       {'string': 'AT+QICSGP=1,1,\"@@DATA@@\",\"\",\"\",0', 'timeout': 3, 'end': 'OK'},
    'docall':       {'string': 'ATD*99#', 'timeout': 3, 'end': 'OK'},

    # TIME
    'gettime':       {'string': 'AT+CCLK?', 'timeout': 3, 'end': '+CCLK'},
    'lts_enable':       {'string': 'AT+CLTS=1', 'timeout': 3, 'end': 'OK'},
    'lts_disable':       {'string': 'AT+CLTS=0', 'timeout': 3, 'end': 'OK'},
    'getlts':       {'string': 'AT+CLTS?', 'timeout': 3, 'end': '+CLTS'},
    
    #GNSS
    'gnss_power_check':       {'string': 'AT+CGNSPWR?', 'timeout': 3, 'end': 'OK'},
    'gnss_power_off':       {'string': 'AT+CGNSPWR=0', 'timeout': 3, 'end': 'OK'},
    'gnss_power_on':       {'string': 'AT+CGNSPWR=1', 'timeout': 3, 'end': 'OK'},
    
    'extended_error': {'string': 'AT+CMEE=2', 'timeout': 3, 'end': 'OK'},
    'extended_error_2': {'string': 'AT+CERR', 'timeout': 30, 'end': 'OK'},

                    
    'setbaud':     {'string':'AT+IPREX=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'setbaud_lte': {'string':'AT+IPR=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'powerdown':   {'string':'AT+CPOWD=1', 'timeout':60, 'end': 'OK'},
    'powerdown_3g':   {'string':'AT+CPOF', 'timeout':60, 'end': 'OK'},
    'adcvoltage':    {'string':'AT+CADC?', 'timeout':3, 'end': 'OK'},
    
    # 0 --> Minimum functionality
    # 1 --> Full functionality
    # 4 --> Disable RF
    # 5 --> Factory test mode
    # 6 --> Restarts module
    # 7 --> Offline mode
    'setfun': {'string':'AT+CFUN=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'getfun': {'string':'AT+CFUN?', 'timeout':3, 'end': 'OK'},
    
    # 2  - Automatic
    # 13 - GSM only
    # 38 - LTE only
    # 51 - GSM and LTE only
    'setprefrerredmode': {'string':'AT+CNMP=@@DATA@@', 'timeout':3, 'end': 'OK'},
    
    
    # 1 - CAT-M
    # 2 - NB-IoT
    # 3 - CAT-M and NB-IoT
    'setprefrerredLTEmode': {'string':'AT+CMNB=@@DATA@@', 'timeout':3, 'end': 'OK'},

    # SIM7070
    'networkregistration':     {'string':'AT+CREG=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'networkregistrationstatus':     {'string':'AT+CGREG=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'getnetworkregistration':     {'string':'AT+CREG?', 'timeout':3, 'end': 'OK'},
    'getnetworkregistrationstatus':     {'string':'AT+CGREG?', 'timeout':3, 'end': 'OK'},
    
    'getnetworkAPN':     {'string':'AT+CGNAPN', 'timeout':3, 'end': 'OK'},
    'getUESystemInformation':     {'string':'AT+CPSI?', 'timeout':3, 'end': 'OK'},
    
    'enableECMAutoconnecting':     {'string':'AT+SECMEN=@@DATA@@', 'timeout':3, 'end': 'OK'},
    'getECMAPNandAuthentication':     {'string':'AT+SECMAUTH?', 'timeout':3, 'end': 'OK'},
    
    # PDP
    'testPDPConfiguration':     {'string':'AT+CNCFG=?', 'timeout':3, 'end': 'OK'},
    'getPDPConfiguration':     {'string':'AT+CNCFG?', 'timeout':3, 'end': 'OK'},
    'setPDPConfiguration':     {'string':'AT+CNCFG=@@DATA@@', 'timeout':3, 'end': 'OK'},


}



class GenericATError(Exception):
    pass


class Response(object):

    def __init__(self, status_code, content):
        self.status_code = int(status_code)
        self.content = content


class AsyncModem(object):


    def __init__(self, uart_port=None, modem_pwkey_pin=None, modem_rst_pin=None, modem_power_on_pin=None, modem_tx_pin=None, modem_rx_pin=None, pwrkey_inverted = True, baudrate = 115200):

        # Pins
        self.MODEM_PWKEY_PIN = modem_pwkey_pin
        self.MODEM_RST_PIN = modem_rst_pin
        self.MODEM_POWER_ON_PIN = modem_power_on_pin
        self.MODEM_TX_PIN = modem_tx_pin
        self.MODEM_RX_PIN = modem_rx_pin
        self.baudrate = baudrate

        self.pwrkey_inverted = pwrkey_inverted
        if pwrkey_inverted:
            self.MODEM_PWKEY_ON = 0
            self.MODEM_PWKEY_OFF = 1
        else:
            self.MODEM_PWKEY_ON = 1
            self.MODEM_PWKEY_OFF = 0

        # The PPP handle.
        self.ppp = None
        self.iccid = None
        self.rssi = None

        # Uart
        # self.uart = uart
        # if uart is not None:
        #     self.swriter = asyncio.StreamWriter(self.uart, {})
        #     self.sreader = asyncio.StreamReader(self.uart)
        # else:
        #     self.swriter = None
        #     self.sreader = None
        self.uart_port = uart_port
        self.uart = None
        self.swriter = None
        self.sreader = None

        self.initialized = False
        self.modem_info = None

        self.ssl_available = None
        


    def debug(self, msg):
        #print(msg)
        _logger.debug(msg)

    # ----------------------
    #  Modem initializer
    # ----------------------


    async def press_modem_powerkey(self, on_pulse_duration_ms=1200):

        print ("press_modem_powerkey({d} [ms])".format(d=on_pulse_duration_ms))

        # Pin initialization
        MODEM_PWKEY_PIN_OBJ = machine.Pin(
            self.MODEM_PWKEY_PIN, machine.Pin.OUT) if self.MODEM_PWKEY_PIN is not None else None
        MODEM_RST_PIN_OBJ = machine.Pin(
            self.MODEM_RST_PIN, machine.Pin.OUT) if self.MODEM_RST_PIN is not None else None
        MODEM_POWER_ON_PIN_OBJ = machine.Pin(
            self.MODEM_POWER_ON_PIN, machine.Pin.OUT) if self.MODEM_POWER_ON_PIN is not None else None
        # MODEM_TX_PIN_OBJ = Pin(self.MODEM_TX_PIN, Pin.OUT) # Not needed as we use MODEM_TX_PIN
        # MODEM_RX_PIN_OBJ = Pin(self.MODEM_RX_PIN, Pin.IN)  # Not needed as we use MODEM_RX_PIN

        # Define pins for unused signal DTR and RI
        #MODEM_DTR_PIN      = 32
        #MODEM_RI_PIN       = 33
        #MODEM_DTR_PIN_OBJ = machine.Pin(MODEM_DTR_PIN, machine.Pin.IN, pull=None) if MODEM_DTR_PIN is not None else None
        #MODEM_RI_PIN_OBJ = machine.Pin(MODEM_RI_PIN, machine.Pin.IN, pull=None) if MODEM_RI_PIN is not None else None

        # Status setup
        if False:
            if MODEM_PWKEY_PIN_OBJ:
                self.debug('Set PWRKEY to 0 ...')
                MODEM_PWKEY_PIN_OBJ.value(self.MODEM_PWKEY_OFF)
            if MODEM_RST_PIN_OBJ:
                self.debug('Set RST to 1 ...')
                MODEM_RST_PIN_OBJ.value(1)
            if MODEM_POWER_ON_PIN_OBJ:
                self.debug('Set POWER_ON to 1 ...')
                MODEM_POWER_ON_PIN_OBJ.value(1)
        

        # Prepare
        if MODEM_RST_PIN_OBJ:
            MODEM_RST_PIN_OBJ.value(0)
        utime.sleep_ms(125)
        if MODEM_RST_PIN_OBJ:
            MODEM_RST_PIN_OBJ.value(1)
            
        if MODEM_PWKEY_PIN_OBJ:
            # Set high level (pwkey off)
            v = self.MODEM_PWKEY_OFF
            print("a MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
            MODEM_PWKEY_PIN_OBJ.value(v)

        # Power ON
        if MODEM_POWER_ON_PIN_OBJ:
            MODEM_POWER_ON_PIN_OBJ.value(1)
        
        await asyncio.sleep_ms(700)
        
        if WDT_ENABLED:
            _wdt.feed()
            
        if MODEM_PWKEY_PIN_OBJ:
            # Set low level (pwkey on)
            v = self.MODEM_PWKEY_ON
            print("a MODEM_PWKEY_PIN ON -> {v}".format(v=v))
            MODEM_PWKEY_PIN_OBJ.value(v)
        await asyncio.sleep_ms(on_pulse_duration_ms)
        
        
        # POWER KEY
        if MODEM_PWKEY_PIN_OBJ:
            # Set high level (pwkey off)ssss
            v = self.MODEM_PWKEY_OFF
            print("a MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
            MODEM_PWKEY_PIN_OBJ.value(v)
        await asyncio.sleep_ms(1800)


        # Set as input so pullup works
        MODEM_PWKEY_PIN_OBJ = machine.Pin(self.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None) if self.MODEM_PWKEY_PIN is not None else None

        if False:
            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(0)
            utime.sleep_ms(125)
            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(1)

    async def receive_any(self):
        # Receive any bytes sent by the modem after powerup to clear buffer
        line = None
        if self.uart.any():
            if DETAILED_DEBUG:
                sys.stdout.write('\b=')
            if USE_ASYNC is False:
                line = self.uart.read()
            else:
                try:
                    line = await asyncio.wait_for(self.sreader.readline(), timeout = 0.250)
                except asyncio.TimeoutError as ex:
                    pass
        else:
            line = None  
        return line

    async def wait_after_modem_powerkey(self):
        global _wdt
        start_ticks_ms = utime.ticks_ms()
        time_gap = 1000
        elapsed_ms = 0
        msg = ""
        if DETAILED_DEBUG:
            #time_gap = 30000
            pass
        
        sys.stdout.write("00000")
        while elapsed_ms < time_gap:
            current_ticks_ms = utime.ticks_ms()
            elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
            await asyncio.sleep_ms(25)
            utime.sleep_ms(250)
            if WDT_ENABLED:
                _wdt.feed() 
            msg = "\b\b\b\b\b{e:05}".format(e=elapsed_ms)
            sys.stdout.write(msg)
            
        print("\n")
        #await self.receive_any()

    async def try_sync(self):
        output = None
        if DETAILED_DEBUG:
            self.debug("Sync ...")
        for i in range(10):
            try:
                output = await self.execute_at_command('syncbaud')
                if 'OK' in output:
                    self.debug("Modem sync succeeded. Output = '{}'".format(output))
                    await asyncio.sleep_ms(4000)
                    return True
                else:
                    if output is not None and len(output):
                        self.debug("Received unexpected output for sync command: '{}'".format(str(output)))
            except:
                pass
        
        return False
        
        
    async def try_get_command_mode(self):       
        try:
            for i in range(2):
                await asyncio.sleep_ms(1200)
                output = await self.execute_at_command('+++')
                await asyncio.sleep_ms(1200)
                if 'OK' in output or 'CFUN' in output or 'CPIN' in output or 'SMS' in output:
                    sync_ok = await self.try_sync()
                    if sync_ok:
                        return True
        except:
            pass
    
        return False


    async def initialize(self):

        self.debug('Initializing modem... ASYNC={a}'.format(a=str(USE_ASYNC)))

        if not self.uart:
            
            import micropython

            # Setup UART
            print(tools.free(True))
            self.debug('Setup modem UART {p} @ {b} bps ...'.format(p=self.uart_port,b=self.baudrate))
            self.uart = machine.UART(self.uart_port, baudrate=self.baudrate, timeout=100, timeout_char=100, rx=self.MODEM_RX_PIN, tx=self.MODEM_TX_PIN)

            gc.collect()
            
            #from generic_async_serial import GenericAsyncSerial
            #await self.powercycle(16000) # RESET
            #await self.powercycle(1200) # Power ON

            start_ticks_ms = utime.ticks_ms()
            elapsed_ms = 0
            

            if self.swriter is not None:
                del self.swriter
            if self.sreader is not None:
                del self.sreader

            if USE_ASYNC:
                self.debug('Setup stream writer and reader ...')
                self.swriter = asyncio.StreamWriter(self.uart, {})
                self.sreader = asyncio.StreamReader(self.uart)
            else:
                self.swriter = None
                self.sreader = None

            #
            # Try to get to command mode and sync
            #

            #sync_ok = await self.try_get_command_mode()
            sync_ok = False
            
            
            idx = 0
            if sync_ok is False:
                #
                # Powercycle and try to sync
                #
                await self.wait_after_modem_powerkey()

                syncbaud_succeeded = False
                while syncbaud_succeeded is False:
                    
                    syncbaud_succeeded = await self.try_sync()

                    if syncbaud_succeeded is False:
                        self.debug("Failed to sync modem -> press modem powerkey to start modem")
                        #
                        # Powercycle again
                        #
                        await self.press_modem_powerkey(1200)
                        await self.wait_after_modem_powerkey()
                        
                        idx = idx +1
                        if idx > 10:
                            # We may be out of memory -> reboot
                            tools.do_reboot()



            self.raw_ppp = raw_ppp(self.uart)

            if False:
                if True:
                    
                    (self.iccid, self.rssi, self.ppp)=self.raw_ppp.demo()
                    #self.raw_ppp.raw_2()
                    
                else:
                    import test.test_ppp as t
                    c = t.InitSimData(self.uart)
                    ppp = c.start()
                    print(ppp.ifconfig())
                    t.test_ppp()

        # Give time to the modem to powerup, to avoid failing at the first modeminfo request
        if WDT_ENABLED:
            _wdt.feed()

        await asyncio.sleep_ms(250)

        if False:

            if DETAILED_DEBUG:
                self.debug("Sync ...")
                for i in range(5):
                    try:
                        await self.execute_at_command('syncbaud')
                    except:
                        pass
            try:
                await self.execute_at_command('syncbaud')
            except:
                pass

            # Test AT commands
            self.debug('Get modem info ...')
            retries = 0
            while True:
                try:
                    if WDT_ENABLED:
                        _wdt.feed()
                    self.modem_info = await self.execute_at_command('modeminfo')
                except Exception as ex:
                    retries += 1
                    if retries < 6:
                        _logger.exc(ex, 
                            'Error in getting modem info {e}, retrying.. (#{r})'.format(e=str(ex), r=retries))
                        # utime.sleep(3)
                        await asyncio.sleep(3)
                    else:
                        raise
                else:
                    break

            self.debug(
                'Ok, modem "{}" is ready and accepting commands'.format(self.modem_info))

        # Set initialized flag and support vars
        self.initialized = True

        # Check if SSL is supported
        if ALLOW_SSL:
            #self.ssl_available = await self.execute_at_command('checkssl') == '+CIPSSL: (0-1)'
            pass
        
        return None

    # ----------------------
    # Execute AT commands
    # ----------------------

    async def execute_at_command(self, command, data=None, clean_output=True):

        """
        ==========
        References
        ==========
        - https://simcom.ee/documents/SIM800/SIM800%20Series_AT%20Command%20Manual_V1.10.pdf
        - https://github.com/olablt/micropython-sim800/blob/4d181f0c5d678143801d191fdd8a60996211ef03/app_sim.py
        - https://arduino.stackexchange.com/questions/23878/what-is-the-proper-way-to-send-data-through-http-using-sim908
        - https://stackoverflow.com/questions/35781962/post-api-rest-with-at-commands-sim800
        - https://arduino.stackexchange.com/questions/34901/http-post-request-in-json-format-using-sim900-module (full post example)
        - https://community.hiveeyes.org/t/unlocking-and-improving-the-pythings-sim800-gprs-module-for-micropython/2978
        - https://community.hiveeyes.org/t/ppp-over-serial-pppos-support-for-micropython-on-esp32/2994
        - https://github.com/loboris/MicroPython_ESP32_psRAM_LoBo/blob/8dbfab5/MicroPython_BUILD/components/micropython/esp32/libs/libGSM.c
        """

        global commands

        command_string = None
        expected_end = None
        timeout = None
        command_string_for_at = None
        line = None
        line_str = None
        output = None

        # Sanity checks
        if command not in commands:
            msg = 'Unknown command "{}"'.format(command)
            _logger.error(msg)
            raise Exception(msg)

        # Support vars
        command_string = commands[command]['string']
        if '@@DATA@@' in command_string:
            if data is not None:
                command_string = command_string.replace('@@DATA@@', str(data))
        expected_end = commands[command]['end']
        timeout = commands[command]['timeout']
        processed_lines = 0

        # Execute the AT command
        command_string_for_at = "{}\r\n".format(command_string)
        self.debug('Writing AT command "{c}" - stack_use = {s} [bytes]'.format(
            c=command_string_for_at.encode('utf-8'), s=micropython.stack_use()))
        
        if USE_ASYNC is False:
            self.uart.write(command_string_for_at)
        else:
            await self.swriter.awrite(command_string_for_at)

        # Support vars
        pre_end = True
        output = ''
        empty_reads = 0

        timeout_ms = timeout *1000
        elapsed_ms = None
        if DETAILED_DEBUG:
            self.debug("Wait for answer ...  ")

        start_ticks_ms = utime.ticks_ms()

        while True:

            if DETAILED_DEBUG:
                sys.stdout.write('\bx')
            if WDT_ENABLED:
                _wdt.feed()

            # Give time to the underlying system to work
            await asyncio.sleep_ms(25)
            utime.sleep_ms(100+SLEEP_MS-25)
            
            if WDT_ENABLED:
                _wdt.feed()

            if DETAILED_DEBUG:
                sys.stdout.write('\b|')
            #line = await asyncio.wait_for(self.sreader.readline(), timeout = 0.250)
            #print("execute_at_command.sreader.readline returned")

            elapsed_ms = 0
            
            while elapsed_ms < timeout_ms and self.uart.any() is False:
                current_ticks_ms = utime.ticks_ms()
                elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
                await asyncio.sleep_ms(25)
                if DETAILED_DEBUG:
                    sys.stdout.write('\b.')
            

            if self.uart.any():
                if DETAILED_DEBUG:
                    sys.stdout.write('\b=')
                if USE_ASYNC is False:
                    line = self.uart.read()
                else:
                    line = await asyncio.wait_for(self.sreader.readline(), timeout = 0.250)
            else:
                line = None

            if DETAILED_DEBUG:
                sys.stdout.write('/')

            if WDT_ENABLED:
                _wdt.feed()


            if not line:
                current_ticks_ms = utime.ticks_ms()
                elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
                if elapsed_ms > timeout_ms:
                    raise Exception(
                        'Timeout for command "{}" (timeout={} [s])'.format(command, timeout))
                    #logger.warning('Timeout for command "{}" (timeout={})'.format(command, timeout))
                    # break
            else:
                
                
                
                len_line = len(line)
                if len_line>128:
                    self.debug('Truncate read line from {l} to 128 characters'.format(l=len_line))
                    line=line[0:128]
                self.debug('Read "{}"'.format(line))

                # Convert line to string
                line_str = line.decode('utf-8')

                if DETAILED_DEBUG:
                    sys.stdout.write('·')

                # Do we have an error?
                if line_str == 'ERROR\r\n':
                    raise GenericATError('Got generic AT error')


                # If we had a pre-end, do we have the expected end?
                if line_str.endswith('{}\r\n'.format(expected_end)):
                    if DETAILED_DEBUG:
                        self.debug('Detected exact end {}'.format(expected_end))
                    output += line_str
                    break
                if pre_end and line_str.startswith('{}'.format(expected_end)):
                    if DETAILED_DEBUG:
                        self.debug(
                            'Detected startwith end (and adding this line to the output too)')
                    output += line_str
                    break

                if '{}'.format(expected_end) in line_str:
                    if DETAILED_DEBUG:
                        self.debug(
                            'Detected expected content {}'.format(expected_end))
                    output += line_str
                    break


                # Do we have a pre-end?
                if line_str == '\r\n':
                    pre_end = True
                    if DETAILED_DEBUG:
                        self.debug('Detected pre-end')
                else:
                    if line_str.endswith('OK\r\n'):
                        pre_end = True
                        if DETAILED_DEBUG:
                            self.debug('Detected pre-end')
                    else:
                        pre_end = False

                if DETAILED_DEBUG:
                    sys.stdout.write('-')

                # Keep track of processed lines and stop if exceeded
                processed_lines += 1

                # Save this line unless in particular conditions
                if command == 'getdata' and line_str.startswith('+HTTPREAD:'):
                    pass
                else:
                    if len(line_str) < 128:
                        output += line_str
                    else:
                        # Truncate
                        output += line_str[0:128]

                if DETAILED_DEBUG:
                    sys.stdout.write("\\")

        if DETAILED_DEBUG:
            self.debug("Cleanup output")

        # Remove the command string from the output
        output = output.replace(command_string+'\r\r\n', '')

        # ..and remove the last \r\n added by the AT protocol
        if output.endswith('\r\n'):
            output = output[:-2]

        # Also, clean output if needed
        if clean_output:
            output = output.replace('\r', '')
            output = output.replace('\n\n', '')
            if output.startswith('\n'):
                output = output[1:]
            if output.endswith('\n'):
                output = output[:-1]

        self.debug('Returning "{}"'.format(output.encode('utf8')))

        # Return
        return output

    # ----------------------
    #  Function commands
    # ----------------------

    async def get_info(self):
        output = await self.execute_at_command('modeminfo')
        return output
    async def get_fwversion(self):
        output = await self.execute_at_command('fwrevision')
        return output        

    async def battery_status(self):
        output = await self.execute_at_command('battery')
        return output

    async def scan_networks(self):
        networks = []
        output = await self.execute_at_command('scan')
        pieces = output.split('(', 1)[1].split(')')
        for piece in pieces:
            piece = piece.replace(',(', '')
            subpieces = piece.split(',')
            if len(subpieces) != 4:
                continue
            networks.append({'name': json.loads(subpieces[1]), 'shortname': json.loads(
                subpieces[2]), 'id': json.loads(subpieces[3])})
        return networks

    async def get_current_network(self):
        output = await self.execute_at_command('network')
        network = output.split(',')[-1]
        if network.startswith('"'):
            network = network[1:]
        if network.endswith('"'):
            network = network[:-1]
        # If after filtering we did not filter anything: there was no network
        if network.startswith('+COPS'):
            return None
        return network

    async def get_signal_strength(self):
        # See more at https://m2msupport.net/m2msupport/atcsq-signal-quality/
        output = await self.execute_at_command('signal')
        signal = int(output.split(':')[1].split(',')[0])
        # 30 is the maximum value (2 is the minimum)
        signal_ratio = float(signal)/float(30)
        return signal_ratio

    async def get_ip_addr(self):
        output = await self.execute_at_command('getbear')
        # Remove potential leftovers in the buffer before the "+SAPBR:" response
        output = output.split('+')[-1]
        pieces = output.split(',')
        if len(pieces) != 3:
            raise Exception(
                'Cannot parse "{}" to get an IP address'.format(output))
        ip_addr = pieces[2].replace('"', '')
        if len(ip_addr.split('.')) != 4:
            raise Exception(
                'Cannot parse "{}" to get an IP address'.format(output))
        if ip_addr == '0.0.0.0':
            return None
        return ip_addr


    async def wait_for_network_registration(self):
        
        is_registered = False
        idx = 0
        output = None
        
        while is_registered is False and idx < 50:
            output = await self.execute_at_command('getnetworkregistration')
            if ('+CREG: 0,5' in output) or ('+CREG: 0,1' in output) :
                _logger.info("Network registration: {r}".format(r=output))
                is_registered = True
                break
            else:
                idx=idx+1
                await asyncio.sleep_ms(100)
        
        return output


    async def wait_for_network_registration_status(self):
        
        is_registered = False
        idx = 0
        output = None
        
        while is_registered is False and idx < 50:
            output = await self.execute_at_command('getnetworkregistrationstatus')
            if ('+CGREG: 0,5' in output) or ('+CGREG: 0,1' in output) :
                _logger.info("Network registration status: {r}".format(r=output))
                is_registered = True
                break
            else:
                idx=idx+1
                await asyncio.sleep_ms(100)
        
        return output



    async def connect(self, apn, user='', pwd=''):
        if not self.initialized:
            raise Exception('Modem is not initialized, cannot connect')

        # Are we already connected?
        ip_addr = await self.get_ip_addr()
        if ip_addr:
            self.debug('Modem is already connected, not reconnecting.')
            return

        # Closing bearer if left opened from a previous connect gone wrong:
        self.debug(
            'Trying to close the bearer in case it was left open somehow..')
        try:
            await self.execute_at_command('closebear')
        except GenericATError:
            pass

        # First, init gprs
        self.debug('Connect step #1 (initgprs)')
        await self.execute_at_command('initgprs')

        # Second, set the APN
        self.debug('Connect step #2 (setapn)')
        await self.execute_at_command('setapn', apn)
        await self.execute_at_command('setuser', user)
        await self.execute_at_command('setpwd', pwd)

        # Then, open the GPRS connection.
        self.debug('Connect step #3 (opengprs)')
        await self.execute_at_command('opengprs')

        # Ok, now wait until we get a valid IP address
        retries = 0
        max_retries = 5
        while True:
            retries += 1
            ip_addr = await self.get_ip_addr()
            if not ip_addr:
                retries += 1
                if retries > max_retries:
                    raise Exception(
                        'Cannot connect modem as could not get a valid IP address')
                self.debug('No valid IP address yet, retrying... (#')
                await asyncio.sleep(1)
            else:
                break

    async def disconnect(self):

        # Close bearer
        try:
            await self.execute_at_command('closebear')
        except GenericATError:
            pass

        # Check that we are actually disconnected
        ip_addr = await self.get_ip_addr()
        if ip_addr:
            raise Exception(
                'Error, we should be disconnected but we still have an IP address ({})'.format(ip_addr))


    def _ppp_cleanup(self):
        # Cleanup
        if self.ppp is not None:
            self.ppp.active(False)
            del self.ppp
            self.ppp = None   

        # Restore streams
        if self.swriter is None:
            self.swriter = asyncio.StreamWriter(self.uart, {})
        if self.sreader is None:
            self.sreader = asyncio.StreamReader(self.uart)




    
    async def ppp_connect_SIM7070(self, apn, user, pwd):
        
        self.iccid =None
        if not self.initialized:
            raise Exception('Modem is not initialized, cannot connect')

        self._ppp_cleanup()

        try:
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))



        if False:
                
            for i in range(5):
                await self.execute_at_command('syncbaud')
                if WDT_ENABLED:
                    _wdt.feed()
                    await asyncio.sleep_ms(SLEEP_MS)
                
            await self.execute_at_command('reset')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
                
            # 'ATE0'
            await self.execute_at_command('echooff')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # 'ATI\r\n'
            await self.execute_at_command('modeminfo')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
            
            # 'AT+CPIN?\r\n'
            await self.execute_at_command('checkpin')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # 'AT+CREG=0\r\n'
            await self.execute_at_command('networkregistration',0)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # 'AT+CGREG=0\r\n'
            await self.execute_at_command('networkregistrationstatus',0)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # 'AT+CFUN=0\r\n'
            await self.execute_at_command('setfun',0)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # 'AT+CFUN=1,1\r\n'
            await self.execute_at_command('setfun','1,1')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
            
            await asyncio.sleep_ms(8000)
            if WDT_ENABLED:
                _wdt.feed()

            # 'AT+CPIN?\r\n'
            await self.execute_at_command('checkpin')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
                
            # 'AT+CFUN=0\r\n'
            await self.execute_at_command('setfun',0)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
                

            # 'AT+CNMP=2\r\n'
            await self.execute_at_command('setprefrerredmode',2)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # 'AT+CMNB=3\r\n'
            await self.execute_at_command('setprefrerredLTEmode',3)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # 'AT+CFUN=0\r\n'
            await self.execute_at_command('setfun',1)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CFUN=?\r\n"
            await self.execute_at_command('getfun')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CREG?\r\n" -> ('+CREG: 0,5' in x) or ('+CREG: 0,1' in x)
            await self.wait_for_network_registration()
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CGREG?\r\n" -> ('+CGREG: 0,5' in x) or ('+CGREG: 0,1' in x)
            await self.wait_for_network_registration_status()
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+CSQ\r\n"
            await self.execute_at_command('signal')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CGNAPN\r\n"
            await self.execute_at_command('getnetworkAPN')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CPSI?\r\n"
            await self.execute_at_command('getUESystemInformation')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+SECMEN=1\r\n"
            await self.execute_at_command('enableECMAutoconnecting',1)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+COPS?\r\n"
            await self.execute_at_command('network')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+CGNAPN\r\n"
            await self.execute_at_command('getnetworkAPN')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
                
                
            # "AT+SECMAUTH?\r\n"
            await self.execute_at_command('getECMAPNandAuthentication')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

            # "AT+CNCFG=?\r\n"
            await self.execute_at_command('testPDPConfiguration')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+CNCFG?\r\n"
            await self.execute_at_command('getPDPConfiguration')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+CNCFG=0,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=APN,u=PPP_USER,p=PPP_PSW)
            pdp_configuration ="0,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=apn,u=user,p=pwd)
            await self.execute_at_command('setPDPConfiguration',pdp_configuration)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+CNCFG?\r\n"
            await self.execute_at_command('getPDPConfiguration')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)


            # "AT+COPS?\r\n"
            await self.execute_at_command('network')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
                
                
                

            # "AT+CSQ\r\n"
            await self.execute_at_command('signal')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)





            await self.execute_at_command('ppp_dial')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)

        else:
            (self.iccid, self.rssi, aux_ppp) = self.raw_ppp.demo(False)


        print("Wait")
        for i in range(4):
            await asyncio.sleep_ms(250)
            if WDT_ENABLED:
                _wdt.feed()

        try:
            print ("Delete stream writer and reader")
            if self.swriter is not None:
                del self.swriter
                self.swriter = None
            if self.sreader is not None:
                del self.sreader
                self.sreader = None
            print("GC")
            gc.collect()
            self.debug("Create network.PPP and activate")
            self.ppp = network.PPP(self.uart)
            self.ppp.active(True)
            self.debug("network.PPP.connect")
            self.ppp.connect(authmode=self.ppp.AUTH_CHAP, username=user, password=pwd)
            #self.ppp.connect(authmode=self.ppp.AUTH_PAP, username=user, password=pwd)

            for i in range(30):
                await asyncio.sleep_ms(250)
                if WDT_ENABLED:
                    _wdt.feed()


            self.debug("Wait for network.PPP connected - stack_use = {s}".format(s=micropython.stack_use()))
            bAlreadyPrinted = False
            b_connected = False
            b_has_ip = False
            c = None
            
            for i in range(4*30):
                b_connected = self.ppp.isconnected()
                ip_cfg = self.ppp.ifconfig()
                print('{i}  - stack_use = {s}, connected = {c}, IP config = {ip_cfg}'.format(i=i, s=micropython.stack_use(), c=str(b_connected), ip_cfg = str(ip_cfg)))
                utime.sleep_ms(100)
                await asyncio.sleep_ms(100)
                if WDT_ENABLED:
                    _wdt.feed()
                b_connected = self.ppp.isconnected()
                if b_connected:
                    print("Connected -> Check IP")
                    ip_cfg = self.ppp.ifconfig()
                    b_has_ip = ip_cfg[0] != "0.0.0.0"
                    if b_has_ip:
                        _logger.info("PPP connected. IP config = {ip_cfg}, iccid={iccid}".format(ip_cfg=str(ip_cfg),iccid=str(self.iccid)))
                        break
                    else:
                        if i>20 and not bAlreadyPrinted:
                            _logger.info("PPP is connected but no IP has been assigned")
                            bAlreadyPrinted = True
                
                if WDT_ENABLED:
                    _wdt.feed()
                await asyncio.sleep_ms(250)
                if WDT_ENABLED:
                    _wdt.feed()                

            if (b_connected and b_has_ip) is False:
                _logger.debug("Failed to connet to PPP -> Cleanup")
                self._ppp_cleanup()

        except Exception as ex:
            _logger.exc(ex,"ppp_connect: {e}".format(e=str(ex)))
            self._ppp_cleanup()
            
        return (self.iccid, self.rssi, self.ppp)
    
    async def ppp_connect(self, apn, user, pwd):
        return await self.ppp_connect_SIM7070(apn, user, pwd)

    async def ppp_disconnect(self):
        if self.ppp is not None:
            self.ppp.active(False)
            del self.ppp
            self.ppp = None        
        if self.swriter is None:
            self.swriter = asyncio.StreamWriter(self.uart, {})
        if self.sreader is None:
            self.sreader = asyncio.StreamReader(self.uart)

        await self.execute_at_command('syncbaud')
        await self.execute_at_command('disconnect')
        await self.execute_at_command('rfoff')



