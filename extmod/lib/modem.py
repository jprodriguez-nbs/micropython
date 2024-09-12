import machine
import time
import umdc_pinout as PINOUT
from machine import UART, Pin

import socket
import utime
import sys
import network
import re
from hwversion import WDT_ENABLED
import tools

if PINOUT.IMPORT_FROM_APP:
    import frozen.umdc_config as CFG
else:
    import umdc_config as CFG


_wdt = None
WDT_ENABLED = True
if WDT_ENABLED:
    _wdt = machine.WDT(timeout=240000)

DEBUG = True
DETAILED_DEBUG = False

try:    
    __config = CFG.config()
    _apn = __config[CFG.K_GPRS][CFG.K_APN]
    _ppp_user = __config[CFG.K_GPRS][CFG.K_USER]
    _ppp_password = __config[CFG.K_GPRS][CFG.K_PSW]
except Exception as ex:
    print("Failed to get PPP configuration from config: {e}".format(e=str(ex)))
    _apn = PINOUT.APN
    _ppp_user = PINOUT.PPP_USER
    _ppp_password = PINOUT.PPP_PSW


def press_modem_powerkey(on_pulse_duration_ms=1200):

    print ("press_modem_powerkey({d} [ms])".format(d=on_pulse_duration_ms))

    # Pin initialization
    MODEM_PWKEY_PIN_OBJ = machine.Pin(
        PINOUT.MODEM_PWKEY_PIN, machine.Pin.OUT) if PINOUT.MODEM_PWKEY_PIN is not None else None
    MODEM_RST_PIN_OBJ = machine.Pin(
        PINOUT.MODEM_RST_PIN, machine.Pin.OUT) if PINOUT.MODEM_RST_PIN is not None else None
    MODEM_POWER_ON_PIN_OBJ = machine.Pin(
        PINOUT.MODEM_POWER_ON_PIN, machine.Pin.OUT) if PINOUT.MODEM_POWER_ON_PIN is not None else None
    

    # Prepare
    if MODEM_RST_PIN_OBJ:
        print ("Modem RST {p} => 0".format(p=PINOUT.MODEM_RST_PIN))
        MODEM_RST_PIN_OBJ.value(0)
        
    utime.sleep_ms(125)
    if MODEM_RST_PIN_OBJ:
        print ("Modem RST {p} => 1".format(p=PINOUT.MODEM_RST_PIN))
        MODEM_RST_PIN_OBJ.value(1)
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)
        v = PINOUT.MODEM_PWKEY_OFF
        print("a MODEM_PWKEY_PIN {p} OFF -> {v}".format(p= PINOUT.MODEM_PWKEY_PIN, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)

    # Power ON
    if MODEM_POWER_ON_PIN_OBJ:
        print ("Modem power {p} ON => 1".format(p=PINOUT.MODEM_POWER_ON_PIN))
        MODEM_POWER_ON_PIN_OBJ.value(1)
    
    utime.sleep_ms(700)
    
    if WDT_ENABLED:
        _wdt.feed()
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set low level (pwkey on)
        v = PINOUT.MODEM_PWKEY_ON
        print("a MODEM_PWKEY_PIN {p} ON -> {v}".format(p= PINOUT.MODEM_PWKEY_PIN, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    utime.sleep_ms(on_pulse_duration_ms)
    
    
    # POWER KEY
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)ssss
        v = PINOUT.MODEM_PWKEY_OFF
        print("a MODEM_PWKEY_PIN {p} OFF -> {v}".format(p= PINOUT.MODEM_PWKEY_PIN, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    utime.sleep_ms(1800)

    # Set as input so pullup works
    #MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None) if PINOUT.MODEM_PWKEY_PIN is not None else None




def get_uart():
    

     #from generic_async_serial import GenericAsyncSerial

    uart_port = PINOUT.MODEM_UART_PORT
    modem_pwkey_pin    = PINOUT.MODEM_PWKEY_PIN
    modem_rst_pin      = PINOUT.MODEM_RST_PIN
    modem_power_on_pin = PINOUT.MODEM_POWER_ON_PIN
    modem_tx_pin       = PINOUT.MODEM_TX_PIN
    modem_rx_pin       = PINOUT.MODEM_RX_PIN
    pwrkey_inverted = PINOUT.PWKEY_INVERTED
    baudrate = PINOUT.MODEM_BAUDRATE    

    if pwrkey_inverted:
        MODEM_PWKEY_ON = 0
        MODEM_PWKEY_OFF = 1
    else:
        MODEM_PWKEY_ON = 1
        MODEM_PWKEY_OFF = 0


    # Pin initialization
    MODEM_PWKEY_PIN_OBJ = machine.Pin(
        modem_pwkey_pin, machine.Pin.OUT) if modem_pwkey_pin is not None else None
    MODEM_RST_PIN_OBJ = machine.Pin(
        modem_rst_pin , machine.Pin.OUT) if modem_rst_pin is not None else None
    MODEM_POWER_ON_PIN_OBJ = machine.Pin(
        modem_power_on_pin, machine.Pin.OUT) if modem_power_on_pin is not None else None
    # MODEM_TX_PIN_OBJ = Pin(self.MODEM_TX_PIN, Pin.OUT) # Not needed as we use MODEM_TX_PIN
    # MODEM_RX_PIN_OBJ = Pin(self.MODEM_RX_PIN, Pin.IN)  # Not needed as we use MODEM_RX_PIN

    # Define pins for unused signal DTR and RI
    MODEM_DTR_PIN_OBJ = machine.Pin(PINOUT.MODEM_DTR_PIN, machine.Pin.IN, pull=None) if PINOUT.MODEM_DTR_PIN is not None else None
    MODEM_RI_PIN_OBJ = machine.Pin(PINOUT.MODEM_RI_PIN, machine.Pin.IN, pull=None) if PINOUT.MODEM_RI_PIN is not None else None


    # Prepare
    if MODEM_RST_PIN_OBJ:
        print ("MODEM RST {p} -> 1".format(p=modem_rst_pin))
        MODEM_RST_PIN_OBJ.value(1)
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)
        v = MODEM_PWKEY_OFF
        print("t MODEM_PWKEY_PIN {p} OFF -> {v}".format(p=modem_pwkey_pin, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)

    # Power ON
    if MODEM_POWER_ON_PIN_OBJ:
        print ("MODEM POWER_ON {p} -> 1".format(p=modem_power_on_pin))
        MODEM_POWER_ON_PIN_OBJ.value(1)
    
    time.sleep(1)
    
    if WDT_ENABLED:
        _wdt.feed()
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set low level (pwkey on)
        v = MODEM_PWKEY_ON
        print("t MODEM_PWKEY_PIN {p} ON -> {v}".format(p=modem_pwkey_pin, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    time.sleep(1)
    
    
    # POWER KEY
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)ssss
        v = MODEM_PWKEY_OFF
        print("MODEM_PWKEY_PIN {p} OFF -> {v}".format(p=modem_pwkey_pin, v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
        

    # Set as input so pullup works
    #MODEM_PWKEY_PIN_OBJ = machine.Pin(modem_pwkey_pin, machine.Pin.IN, pull=None) if modem_pwkey_pin is not None else None

    if MODEM_RST_PIN_OBJ:
        print ("MODEM RST {p} -> 0".format(p=modem_rst_pin))
        MODEM_RST_PIN_OBJ.value(0)

    start_ticks_ms = utime.ticks_ms()
    elapsed_ms = 0
    

    # Setup UART
    print('Modem PPP - Setup modem UART {p} ...'.format(p=uart_port))

    gsm = None
    try:
        gsm = machine.UART(uart_port, baudrate=baudrate, timeout=250, timeout_char=100, rx=modem_rx_pin, tx=modem_tx_pin)
    except Exception as E:
        print("Modem: Failed to open uart {p} with rx {rx} and tx {tx}: {e}".format(p=uart_port,rx=modem_rx_pin, tx=modem_tx_pin, e=str(E)))


    utime.sleep_ms(125)
    if MODEM_RST_PIN_OBJ:
        print ("MODEM RST {p} -> 1".format(p=modem_rst_pin))
        MODEM_RST_PIN_OBJ.value(1)

    time_gap = 5000
    if DETAILED_DEBUG:
        #time_gap = 30000
        pass
    
    sys.stdout.write("00000")
    while elapsed_ms < time_gap:
        current_ticks_ms = utime.ticks_ms()
        elapsed_ms = utime.ticks_diff(current_ticks_ms, start_ticks_ms)
        time.sleep(1)
        if WDT_ENABLED:
            _wdt.feed() 
        msg = "\b\b\b\b\b{e:05}".format(e=elapsed_ms)
        sys.stdout.write(msg)
    print("\n")
    
    
    return gsm


class Modem():
    def __init__(self, gsm):
        if gsm is None:
            gsm = get_uart()
        self.gsm = gsm
        
    def empty_buffer(self):
        # Empty buffer
        #return
        status = "Full"
        while status is not None and len(status)>0:
            status = self.gsm.readline()
            if WDT_ENABLED:
                _wdt.feed()
            if status is not None:
                try:
                    #status = status.decode().replace('\r\n','')
                    if DETAILED_DEBUG: print('E  ', status)
                except:
                    pass
    

    def read_status(self):
        status = self.gsm.readline()
        if WDT_ENABLED:
            _wdt.feed()
        if status is not None:
            if DETAILED_DEBUG: print('S1 ', str(status))
            pass
        if status is None or len(status)==0:
            status = self.gsm.readline()
            if status is not None:
                if DETAILED_DEBUG: print('S2 ', str(status))
                pass
        if status:
            try:
                status = status.decode().replace('\r\n','')
                #status = status.decode()
            except Exception as ex:
                status = None
            return status
        else:
            pass


    def read_first(self):
        status = self.gsm.readline()
        if WDT_ENABLED:
            _wdt.feed()
        if status:
            try:
                if DETAILED_DEBUG: print('F  ', str(status))
                status = status.decode().replace('\r\n','')
                #status = status.decode()
            except Exception as ex:
                status = None
            return status
        else:
            pass

    def command(self, c, timeout=3, ans_rx_pattern=None, debug=DEBUG):
        ts_start = utime.time()
        first = True
        if ans_rx_pattern is not None:
            rx = re.compile(ans_rx_pattern)
        else:
            rx = None
        self.empty_buffer()        
        while True:
            buffer = ""
            cmd = "{command}\r\n".format(command=c)
            if first:
                if DEBUG: print ("Write ",c)
                first = False
            self.gsm.write(cmd)
            if WDT_ENABLED:
                _wdt.feed()
            status = self.read_first()
            while status is not None:
                if DEBUG and len(status): print(status)
                buffer = buffer + status
                if rx is None:
                    if len(buffer)>0:
                        return (True, None)
                else:
                    m = rx.search(buffer)
                    if DETAILED_DEBUG: 
                        m_result = str(m) + " - Matched" if m else " - NO MATCH"
                        print("\n-----\n{mr} \n'{b}'\n with \n'{r}'\n-----\n".format(mr=m_result, r=ans_rx_pattern, b=buffer))
                        if m:
                            g_idx = 1
                            while True:
                                try:
                                    print("Group {i} -> '{v}'".format(i=g_idx, v=m.group(g_idx)))
                                    g_idx+=1
                                except:
                                    break
                    if m:
                        # Get result
                        self.empty_buffer()
                        return (True, m)
                # Read next
                status = self.read_first()
                
            else:
                pass
            ts_now = utime.time()
            elapsed_s = ts_now - ts_start
            if elapsed_s > timeout:
                # Command failed to get an answer
                break
        
        return (False, None)
            
                
    def commands(self, li):
        for c in li:
            self.command(c)
            
    def attachGSMtoPPP(self):
        
        self.empty_buffer()
        

        
        is_connected = False
        while is_connected is False:
            print("Create network.PPP")
            GPRS=network.PPP(self.gsm)
            time.sleep(1)
            print("Activate network.PPP")
            GPRS.active(True)
            time.sleep(1)
            print("Connect network.PPP with '{u}', '{p}'".format(u=_ppp_user, p=_ppp_password))
            GPRS.connect(authmode=GPRS.AUTH_CHAP, username=_ppp_user, password=_ppp_password)
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
                    #self.attachGSMtoPPP()

            if is_connected is False:
                GPRS.active(False)
                time.sleep(1)
                del GPRS
                GPRS = None

        return GPRS
    
    def calc_rssi(self, m):
        rssi = None
        ber = None
        try:
            if m:
                rssi_raw = int(m.group(1))
                ber = m.group(2)
                
                if rssi_raw == 0:
                    rssi = -115
                elif rssi_raw == 1:
                    rssi = -111
                elif rssi_raw <= 30:
                    rssi = -110 + ((rssi_raw-2)*56)/28
                elif rssi_raw == 31:
                    rssi = -52
                else:
                    # Unknown or not detectable
                    rssi = None
        except Exception as ex:
            print ("Exception: {e}".format(e=str(ex)))
        return (rssi, ber)
    
    
    def get_group(self, m, g):
        r = None
        if m:
            try:
                r = m.group(g)
            except:
                pass
        return r
    
    def connect(self, apn="clnxpt.vf.global", user="Portugal", pwd="1234RTU"):
        (sync, status) = self.command('AT')
        max_cycles = 4
        idx = 0
        while sync is False and idx<max_cycles:
            press_modem_powerkey()
            sync = self.command('AT',4)
            sync = self.command('AT',4)
            idx = idx + 1
        
        if sync is False:
            machine.reset()
              
        PINOUT.ExecuteModemInitialCommands(self, __config)
              
        li_commands = PINOUT.GetPPPCommands(apn, user, pwd)
                             
        self.commands(li_commands)
        
        time.sleep(8)
        
        (csq_result, csq_status_m) = self.command('AT+CSQ', 5, 'CSQ:\s*(\d+),(\d+)')
        (rssi, ber) = self.calc_rssi(csq_status_m)
        print ('CSQ -> {r} {s} dBm'.format(r=csq_result, s=rssi))
        
        cereg_result = False
        cgreg_result = False
        cereg_status_m = None
        cgreg_status_m = None
        (cereg_result, cereg_status_m) = self.command('AT+CEREG?', 2, 'CEREG: (0,[15])')
        
        for idx in range(50):
            if PINOUT.WAIT_FOR_CREG:
                if not cereg_result:
                    (cereg_result, cereg_status_m) = self.command('AT+CEREG?', 2, 'CEREG: (0,[15])')
            if not cgreg_result:
                (cgreg_result, cgreg_status_m) = self.command('AT+CGREG?', 2, 'CGREG: (0,[15])')
            if (PINOUT.WAIT_FOR_CREG is False or cereg_result) and cgreg_result:
                break
        
        (addr_result, addr_status_m) = self.command('AT+CGPADDR=1', 5, 'CGPADDR:\s*(\w+),(\w+)?')
        (cpin_result, cpin_status_m) = self.command('AT+CPIN?', 5, 'CPIN:\s*(\w+)')
        (iccid_result, iccid_status_m) = self.command('AT+CCID', 5, '(CCID\s*)?(\d+)')
        (imei_result, imei_status_m) = self.command('AT+GSN', 5, '(GSN\s*)?(\d+)')
        (gmr_result, gmr_status_m) = self.command('AT+GMR', 5, 'Revision:(\w+)')
        (cpsi_result, cpsi_status_m) = self.command('AT+CPSI?', 5, 'CPSI:\s*([\s\w,-\.]+)')
        (csq_result, csq_status_m) = self.command('AT+CSQ', 5, 'CSQ:\s*(\d+),(\d+)')
        
        cpin_status = self.get_group(cpin_status_m,1)
        revision = self.get_group(gmr_status_m,1)
        (rssi, ber) = self.calc_rssi(csq_status_m)
        iccid = self.get_group(iccid_status_m,2)
        imei = self.get_group(imei_status_m,2)
        addr = self.get_group(addr_status_m,2)
        cpsi = self.get_group(cpsi_status_m,1)
        
        if cereg_status_m is not None:
            creg = self.get_group(cereg_status_m,0)
        else:
            creg = None
            
        if cgreg_status_m is not None:
            cgreg = self.get_group(cgreg_status_m,0)
        else:
            cgreg = None
        
        print ('PIN -> {r} {s}'.format(r=cpin_result, s=cpin_status))
        print ('GMR -> {r} {s}'.format(r=gmr_result, s=revision))
        print ('CSQ -> {r} {s} dBm'.format(r=csq_result, s=rssi))
        print ('CCID (ICCID) -> {r} {s}'.format(r=iccid_result, s=iccid))
        print ('GSN (IMEI) -> {r} {s}'.format(r=imei_result, s=imei))
        print ('ADDR -> {r} {s}'.format(r=addr_result, s=addr))
        print ('CPSI -> {r} {s}'.format(r=cpsi_result, s=cpsi))
        print ('CEREG -> {r} {s}'.format(r=cereg_result, s=creg))
        print ('CGREG -> {r} {s}'.format(r=cgreg_result, s=cgreg))
        
        self.commands(['AT+CGACT?'])
        
        
        PINOUT.ExecuteModemLastCommandsBeforePPP(self, __config)
        
        (connect_result, connect_status_m) = self.command('ATD*99#', 10, 'CONNECT\s?(\d*)?')
        if connect_status_m is not None:
            connect_speeed = self.get_group(connect_status_m,1)
        else:
            connect_speeed = None
        print ('ATD -> {r} {s}'.format(r=connect_result, s=connect_speeed))
        
                
        self.empty_buffer()
        
        #tools.free()
        #ppp = self.attachGSMtoPPP()
        
        tools.free()
        
        return (iccid, imei, rssi, revision, self.gsm)

    def disconnect(self):
        press_modem_powerkey()
        pass