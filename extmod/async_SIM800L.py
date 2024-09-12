# Imports
import time
import json
from app.planter_pinout import WDT_ENABLED
import utime

import logging as logging
import uasyncio as asyncio
import timetools
import machine
import micropython
import network
import time
import hwversion

import gc
import sys

SLEEP_MS = 100

_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

WDT_ENABLED = hwversion.WDT_ENABLED
if WDT_ENABLED:
    _wdt = machine.WDT(timeout=240000)

ALLOW_SSL = True

# Commands dictionary. Not the best approach ever, but works nicely.
commands = {
    # General commands
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
    'syncbaud':    {'string': 'AT', 'timeout': 3, 'end': 'OK'},
    'reset':       {'string': 'ATZ', 'timeout': 3, 'end': 'OK'},
    'disconnect':  {'string': 'ATH', 'timeout': 20, 'end': 'OK'},   # Use "NO CARRIER" here?
    'checkpin':    {'string': 'AT+CPIN?', 'timeout': 3, 'end': '+CPIN: READY'},
    'nosms':       {'string': 'AT+CNMI=0,0,0,0,0', 'timeout': 3, 'end': 'OK'},
    'ppp_setapn':  {'string': 'AT+CGDCONT=1,"IP","@@DATA@@"', 'timeout': 3, 'end': 'OK'},
    'getipdetails':  {'string': 'AT+CGDCONT?', 'timeout': 3, 'end': 'OK'},
    'ppp_connect': {'string': 'AT+CGDATA="PPP",1', 'timeout': 3, 'end': 'CONNECT'},
    'rfon':        {'string': 'AT+CFUN=1', 'timeout': 3, 'end': 'OK'},
    'rfoff':       {'string': 'AT+CFUN=4', 'timeout': 3, 'end': 'OK'},
    'echoon':      {'string': 'ATE1', 'timeout': 3, 'end': 'OK'},
    'echooff':     {'string': 'ATE0', 'timeout': 3, 'end': 'OK'},

    'creg0':       {'string': 'AT+CREG0', 'timeout': 3, 'end': 'OK'},
    'cgreg0':       {'string': 'AT+CREG0', 'timeout': 3, 'end': 'OK'},
    'qicsgp':       {'string': 'AT+QICSGP=1,1,\"clnxpt.vf.global\",\"\",\"\",0', 'timeout': 3, 'end': 'OK'},
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

}



class GenericATError(Exception):
    pass


class Response(object):

    def __init__(self, status_code, content):
        self.status_code = int(status_code)
        self.content = content


class AsyncModem(object):

    def __init__(self, uart=None, modem_pwkey_pin=None, modem_rst_pin=None, modem_power_on_pin=None, modem_tx_pin=None, modem_rx_pin=None):

        # Pins
        self.MODEM_PWKEY_PIN = modem_pwkey_pin
        self.MODEM_RST_PIN = modem_rst_pin
        self.MODEM_POWER_ON_PIN = modem_power_on_pin
        self.MODEM_TX_PIN = modem_tx_pin
        self.MODEM_RX_PIN = modem_rx_pin

        # The PPP handle.
        self.ppp = None

        # Uart
        self.uart = uart
        if uart is not None:
            self.swriter = asyncio.StreamWriter(self.uart, {})
            self.sreader = asyncio.StreamReader(self.uart)
        else:
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

    async def initialize(self):

        self.debug('Initializing modem...')

        if not self.uart:
            from machine import UART, Pin
            #from generic_async_serial import GenericAsyncSerial

            # Pin initialization
            MODEM_PWKEY_PIN_OBJ = Pin(
                self.MODEM_PWKEY_PIN, Pin.OUT) if self.MODEM_PWKEY_PIN is not None else None
            MODEM_RST_PIN_OBJ = Pin(
                self.MODEM_RST_PIN, Pin.OUT) if self.MODEM_RST_PIN is not None else None
            MODEM_POWER_ON_PIN_OBJ = Pin(
                self.MODEM_POWER_ON_PIN, Pin.OUT) if self.MODEM_POWER_ON_PIN else None
            # MODEM_TX_PIN_OBJ = Pin(self.MODEM_TX_PIN, Pin.OUT) # Not needed as we use MODEM_TX_PIN
            # MODEM_RX_PIN_OBJ = Pin(self.MODEM_RX_PIN, Pin.IN)  # Not needed as we use MODEM_RX_PIN

            # Define pins for unused signal DTR and RI
            MODEM_DTR_PIN      = 32
            MODEM_RI_PIN       = 33
            MODEM_DTR_PIN_OBJ = Pin(MODEM_DTR_PIN, Pin.IN, pull=None) if self.MODEM_DTR_PIN is not None else None
            MODEM_RI_PIN_OBJ = Pin(MODEM_RI_PIN, Pin.IN, pull=None) if self.MODEM_RI_PIN is not None else None

            # Status setup
            if False:
                if MODEM_PWKEY_PIN_OBJ:
                    self.debug('Set PWKEY to 0 ...')
                    MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
                if MODEM_RST_PIN_OBJ:
                    self.debug('Set RST to 1 ...')
                    MODEM_RST_PIN_OBJ.value(1)
                if MODEM_POWER_ON_PIN_OBJ:
                    self.debug('Set POWER_ON to 1 ...')
                    MODEM_POWER_ON_PIN_OBJ.value(1)
            

            # Prepare
            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(1)
            if MODEM_PWKEY_PIN_OBJ:
                MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)

            # Power ON
            if MODEM_POWER_ON_PIN_OBJ:
                MODEM_POWER_ON_PIN_OBJ.value(1)
            await asyncio.sleep_ms(700)
            if WDT_ENABLED:
                _wdt.feed()

            # POWER KEY
            if MODEM_PWKEY_PIN_OBJ:
                MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_ON)

            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(0)

            start_ticks_ms = utime.ticks_ms()
            elapsed_ms = 0
            

            # Setup UART
            self.debug('Setup modem UART ...')

            # Pycom
            # https://docs.pycom.io/firmwareapi/pycom/machine/uart/
            if sys.platform in ['WiPy', 'LoPy', 'LoPy4', 'SiPy', 'GPy', 'FiPy']:
                self.uart = UART(1, baudrate=9600, pins=(self.MODEM_RX_PIN, self.MODEM_TX_PIN))

            # Genuine MicroPython
            # http://docs.micropython.org/en/latest/library/pyb.UART.html
            else:
                #self.uart = UART(1, 115200, timeout=250, rx=self.MODEM_TX_PIN, tx=self.MODEM_RX_PIN, txbuf=2048, rxbuf=10000)
                self.uart = UART(1, 115200, timeout=250, timeout_char=250, rx=self.MODEM_TX_PIN, tx=self.MODEM_RX_PIN)

            if self.swriter is not None:
                del self.swriter
            if self.sreader is not None:
                del self.sreader

            self.swriter = asyncio.StreamWriter(self.uart, {})
            self.sreader = asyncio.StreamReader(self.uart)

            utime.sleep_ms(125)
            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(1)

            sys.stdout.write("00000")
            while elapsed_ms < 30000:
                current_ticks_ms = utime.ticks_ms()
                elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
                await asyncio.sleep_ms(25)
                utime.sleep_ms(250)
                if WDT_ENABLED:
                    _wdt.feed() 
                msg = "\b\b\b\b\b{e:05}".format(e=elapsed_ms)
                sys.stdout.write(msg)




        # Give time to the modem to powerup, to avoid failing at the first modeminfo request
        if WDT_ENABLED:
            _wdt.feed()

        await asyncio.sleep_ms(250)

        self.debug("Sync ...")
        try:
            await self.execute_at_command('syncbaud')
        except:
            pass
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
                        'Error in getting modem info, retrying.. (#{})'.format(retries))
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
            self.ssl_available = await self.execute_at_command('checkssl') == '+CIPSSL: (0-1)'

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
                command_string = command_string.replace('@@DATA@@', data)
        expected_end = commands[command]['end']
        timeout = commands[command]['timeout']
        processed_lines = 0

        # Execute the AT command
        command_string_for_at = "{}\r\n".format(command_string)
        self.debug('Writing AT command "{c}" - stack_use = {s} [bytes]'.format(
            c=command_string_for_at.encode('utf-8'), s=micropython.stack_use()))
        # self.uart.write(command_string_for_at)
        await self.swriter.awrite(command_string_for_at)

        # Support vars
        pre_end = True
        output = ''
        empty_reads = 0

        timeout_ms = timeout *1000
        elapsed_ms = None
        self.debug("Wait for answer ...")

        start_ticks_ms = utime.ticks_ms()

        while True:

            sys.stdout.write('x')
            if WDT_ENABLED:
                _wdt.feed()

            # Give time to the underlying system to work
            await asyncio.sleep_ms(25)
            utime.sleep_ms(100+SLEEP_MS-25)
            
            if WDT_ENABLED:
                _wdt.feed()

            sys.stdout.write('|')
            #line = await asyncio.wait_for(self.sreader.readline(), timeout = 0.250)
            #print("execute_at_command.sreader.readline returned")

            elapsed_ms = 0
            
            while elapsed_ms < timeout_ms and self.uart.any() is False:
                current_ticks_ms = utime.ticks_ms()
                elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
                await asyncio.sleep_ms(25)
                sys.stdout.write('.')
            if self.uart.any():
                sys.stdout.write('=')
                line = await asyncio.wait_for(self.sreader.readline(), timeout = 0.250)
            else:
                line = None

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

                sys.stdout.write('·')

                # Do we have an error?
                if line_str == 'ERROR\r\n':
                    raise GenericATError('Got generic AT error')

                # If we had a pre-end, do we have the expected end?
                if line_str == '{}\r\n'.format(expected_end):
                    self.debug('Detected exact end')
                    break
                if pre_end and line_str.startswith('{}'.format(expected_end)):
                    self.debug(
                        'Detected startwith end (and adding this line to the output too)')
                    output += line_str
                    break

                # Do we have a pre-end?
                if line_str == '\r\n':
                    pre_end = True
                    self.debug('Detected pre-end')
                else:
                    if line_str == 'OK\r\n':
                        pre_end = True
                        self.debug('Detected pre-end')
                    else:
                        pre_end = False

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

                sys.stdout.write("\\")

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

    async def http_request(self, url, mode='GET', data=None, content_type='application/json'):

        # Protocol check.
        assert url.startswith(
            'http'), 'Unable to handle communication protocol for URL "{}"'.format(url)

        # Are we  connected?
        ip_addr = await self.get_ip_addr()
        if not ip_addr:
            raise Exception('Error, modem is not connected')

        # Close the http context if left open somehow
        self.debug('Close the http context if left open somehow...')
        try:
            await self.execute_at_command('closehttp')
        except GenericATError:
            pass

        # First, init and set http
        self.debug('Http request step #1.1 (inithttp)')
        await self.execute_at_command('inithttp')
        self.debug('Http request step #1.2 (sethttp)')
        await self.execute_at_command('sethttp')

        # Do we have to enable ssl as well?
        if ALLOW_SSL and self.ssl_available:
            if url.startswith('https://'):
                self.debug('Http request step #1.3 (enablessl)')
                await self.execute_at_command('enablessl')
            elif url.startswith('http://'):
                self.debug('Http request step #1.3 (disablessl)')
                await self.execute_at_command('disablessl')
        else:
            if url.startswith('https://'):
                raise NotImplementedError(
                    "SSL is only supported by firmware revisions >= R14.00")

        # Second, init and execute the request
        self.debug('Http request step #2.1 (initurl)')
        await self.execute_at_command('initurl', data=url)

        if mode == 'GET':

            self.debug('Http request step #2.2 (doget)')
            output = await self.execute_at_command('doget')
            response_status_code = output.split(',')[1]
            self.debug('Response status code: "{}"'.format(
                response_status_code))

        elif mode == 'POST':

            self.debug('Http request step #2.2 (setcontent)')
            await self.execute_at_command('setcontent', content_type)

            self.debug('Http request step #2.3 (postlen)')
            await self.execute_at_command('postlen', len(data))

            self.debug('Http request step #2.4 (dumpdata)')
            await self.execute_at_command('dumpdata', data)

            self.debug('Http request step #2.5 (dopost)')
            output = await self.execute_at_command('dopost')
            response_status_code = output.split(',')[1]
            self.debug('Response status code: "{}"'.format(
                response_status_code))

        else:
            raise Exception('Unknown mode "{}'.format(mode))

        # Third, get data
        self.debug('Http request step #4 (getdata)')
        response_content = await self.execute_at_command('getdata', clean_output=False)

        self.debug(response_content)

        # Then, close the http context
        self.debug('Http request step #4 (closehttp)')
        await self.execute_at_command('closehttp')

        return Response(status_code=response_status_code, content=response_content)

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


    async def ppp_connect(self, apn, user, pwd):

        if not self.initialized:
            raise Exception('Modem is not initialized, cannot connect')

        self._ppp_cleanup()

        try:
            #await self.execute_at_command('extended_error')
            #await self.execute_at_command('extended_error_2')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))

        await self.execute_at_command('syncbaud')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)
        await self.execute_at_command('reset')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)
        await self.execute_at_command('echooff')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)

        try:
            await self.execute_at_command('lts_enable') # JP
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))

        await self.execute_at_command('rfon')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)

        try:
            await asyncio.sleep_ms(500)
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(50)
            #await self.execute_at_command('extended_error_2')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
            await self.execute_at_command('checkpin')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))
            try:
                #await self.execute_at_command('extended_error')
                #await self.execute_at_command('extended_error_2')
                if WDT_ENABLED:
                    _wdt.feed()
                    await asyncio.sleep_ms(SLEEP_MS)
            except Exception as ex:
                _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))


        try:
            await self.execute_at_command('checkreg')
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))

        try:
            await self.execute_at_command('network') # JP
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
            await self.execute_at_command('signal') # JP
            if WDT_ENABLED:
                _wdt.feed()
                await asyncio.sleep_ms(SLEEP_MS)
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))
        

        try:
            ts_now = utime.time()
            if ts_now < 601432115:
                if WDT_ENABLED:
                    _wdt.feed()
                await self.execute_at_command('getlts') # JP
                await asyncio.sleep_ms(200)
                dt = await self.execute_at_command('gettime') # JP
                if "CCLK:" in dt:
                    dt = dt.split("\"")[1]
                    ts = timetools.grpsdt2timestamp(dt)
                    tm = utime.localtime(ts)
                    tm = tm[0:3] + (0,) + tm[3:6] + (0,)
                    rtc = machine.RTC()
                    rtc.datetime(tm)
                    _logger.info("GPRS datetime: '{dt}'".format(dt=dt))
        except Exception as ex:
            _logger.exc(ex,"Modem error: {e}".format(e=str(ex)))

        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)
        await self.execute_at_command('nosms')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)
        await self.execute_at_command('ppp_setapn', apn)
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)
        await self.execute_at_command('ppp_connect')
        if WDT_ENABLED:
            _wdt.feed()
            await asyncio.sleep_ms(SLEEP_MS)

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
            self.ppp.connect(authmode=self.ppp.AUTH_PAP, username=user, password=pwd)

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
                print('{i}  - stack_use = {s}'.format(i=i, s=micropython.stack_use()))
                utime.sleep_ms(100)
                await asyncio.sleep_ms(100)
                if WDT_ENABLED:
                    _wdt.feed()
                b_connected = self.ppp.isconnected()
                if b_connected:
                    print("Connected -> Check IP")
                    c = self.ppp.ifconfig()
                    b_has_ip = c[0] != "0.0.0.0"
                    if b_has_ip:
                        _logger.info("PPP connected. IP config = {c}".format(c=str(c)))
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
            
        return self.ppp

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

