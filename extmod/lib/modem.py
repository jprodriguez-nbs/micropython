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


_wdt = None
WDT_ENABLED = True
if WDT_ENABLED:
    _wdt = machine.WDT(timeout=240000)

DEBUG = True
DETAILED_DEBUG = False

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
        MODEM_RST_PIN_OBJ.value(0)
    utime.sleep_ms(125)
    if MODEM_RST_PIN_OBJ:
        MODEM_RST_PIN_OBJ.value(1)
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)
        v = PINOUT.MODEM_PWKEY_OFF
        print("a MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)

    # Power ON
    if MODEM_POWER_ON_PIN_OBJ:
        MODEM_POWER_ON_PIN_OBJ.value(1)
    
    utime.sleep_ms(700)
    
    if WDT_ENABLED:
        _wdt.feed()
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set low level (pwkey on)
        v = PINOUT.MODEM_PWKEY_ON
        print("a MODEM_PWKEY_PIN ON -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    utime.sleep_ms(on_pulse_duration_ms)
    
    
    # POWER KEY
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)ssss
        v = PINOUT.MODEM_PWKEY_OFF
        print("a MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    utime.sleep_ms(1800)

    # Set as input so pullup works
    MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None) if PINOUT.MODEM_PWKEY_PIN is not None else None




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
    MODEM_DTR_PIN      = 32
    MODEM_RI_PIN       = 33
    MODEM_DTR_PIN_OBJ = machine.Pin(MODEM_DTR_PIN, machine.Pin.IN, pull=None) if MODEM_DTR_PIN is not None else None
    MODEM_RI_PIN_OBJ = machine.Pin(MODEM_RI_PIN, machine.Pin.IN, pull=None) if MODEM_RI_PIN is not None else None


    # Prepare
    if MODEM_RST_PIN_OBJ:
        MODEM_RST_PIN_OBJ.value(1)
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)
        v = MODEM_PWKEY_OFF
        print("t MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)

    # Power ON
    if MODEM_POWER_ON_PIN_OBJ:
        MODEM_POWER_ON_PIN_OBJ.value(1)
    
    time.sleep(1)
    
    if WDT_ENABLED:
        _wdt.feed()
        
    if MODEM_PWKEY_PIN_OBJ:
        # Set low level (pwkey on)
        v = MODEM_PWKEY_ON
        print("t MODEM_PWKEY_PIN ON -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
    time.sleep(1)
    
    
    # POWER KEY
    if MODEM_PWKEY_PIN_OBJ:
        # Set high level (pwkey off)ssss
        v = MODEM_PWKEY_OFF
        print("MODEM_PWKEY_PIN OFF -> {v}".format(v=v))
        MODEM_PWKEY_PIN_OBJ.value(v)
        

    # Set as input so pullup works
    MODEM_PWKEY_PIN_OBJ = machine.Pin(modem_pwkey_pin, machine.Pin.IN, pull=None) if modem_pwkey_pin is not None else None

    if MODEM_RST_PIN_OBJ:
        MODEM_RST_PIN_OBJ.value(0)

    start_ticks_ms = utime.ticks_ms()
    elapsed_ms = 0
    

    # Setup UART
    print('Modem PPP - Setup modem UART {p} ...'.format(p=uart_port))

    gsm = machine.UART(uart_port, baudrate=baudrate, timeout=250, timeout_char=100, rx=modem_rx_pin, tx=modem_tx_pin)


    utime.sleep_ms(125)
    if MODEM_RST_PIN_OBJ:
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
            r = m.group(g)
        return r
    
    def connect(self, apn="clnxpt.vf.global", user="Portugal", pwd="1234RTU"):
        (sync, status) = self.command('AT')
        max_cycles = 10
        idx = 0
        while sync is False:
            press_modem_powerkey()
            sync = self.command('AT',4)
        
        if sync is False:
            machine.reset()
                    
        # 'AT+CNCFG=?', 'AT+CNCFG=0,0,"clnxpt.vf.global","Portugal","1234RTU",3'
        # apn_cfg = 'AT+CNCFG=0,0,"{a}","{u}","{p}",3'.format(a=apn, u=user,p=pwd) # PAP and CHAP
        apn_cfg = 'AT+CNCFG=0,0,"{a}","{u}","{p}",2'.format(a=apn, u=user,p=pwd) # Only CHAP
        #pdp_auth_cfg = 'AT+CGAUTH=0,2,"{p}","{u}"'.format(u=user,p=pwd) # Only CHAP
        
                    
        self.commands(['AT', 'ATE0', 'AT+CPIN?', 'AT+CREG=0', 'AT+CGREG=0', 'AT+CFUN=0', 'ATE0', 'ATE0', 'ATE0', 'ATE0', 'AT+CFUN=1,1', 'ATE0', 'ATE0', 'ATE0', 'ATE0', 'ATE0', 'ATE0', 'AT+CPIN?', 'AT+CFUN=0', 'ATE0', 'ATE0', 'ATE0', 'AT+CNMP=51', 'AT+CMNB=2', apn_cfg,'AT+CFUN=1', 'ATE0', 'ATE0', 'ATE0', 'AT+CFUN=?', 'AT+GMR', 'AT+GSN', 'AT+CREG?', 'AT+CGREG?'])
        self.commands(['AT+CFUN=0', 'ATE0', 'ATE0', 'ATE0','AT+CGDCONT=?', 'AT+CGDCONT=1,"IP",""', 'AT+CNMP=?', 'AT+CNMP=51', 'AT+CMNB=?', 'AT+CMNB=2','AT+CNCFG=?',apn_cfg,'AT+CFUN=1', 'ATE0', 'ATE0', 'ATE0'])
        
        self.commands(['AT+CSQ', 'AT+CGNAPN', 'AT+CPSI?', 'AT+SECMEN=1', 'AT+COPS?', 'AT+CGNAPN', 'AT+SECMAUTH?', apn_cfg, 'AT+CGATT?', 'AT+CGNAPN'])
        self.commands(['AT+CNACT=?','AT+CNACT?','AT+CNACT=0,2','AT+CNACT?'])
        
        (csq_result, csq_status_m) = self.command('AT+CSQ', 5, 'CSQ:\s*(\d+),(\d+)')
        (rssi, ber) = self.calc_rssi(csq_status_m)
        print ('CSQ -> {r} {s} dBm'.format(r=csq_result, s=rssi))
        
        self.commands(['AT+CNCFG?', 'AT+GMM', 'AT+CCID', 'AT+COPS?', 'AT+CSQ', 'AT+CREG?', 'AT+CGREG?', 'AT+CFUN?','AT+CPIN?', 'AT+COPS?', 'AT+CSQ', 'AT+CREG?', 'AT+CGREG?','AT+CNACT?'])
        
        (cpin_result, cpin_status_m) = self.command('AT+CPIN?', 5, 'CPIN:\s*(\w+)')
        (iccid_result, iccid_status_m) = self.command('AT+CCID', 5, '(CCID\s*)?(\d+)')
        (imei_result, imei_status_m) = self.command('AT+GSN', 5, '(GSN\s*)?(\d+)')
        (gmr_result, gmr_status_m) = self.command('AT+GMR', 5, 'Revision:(\w+)')

        
        creg_result = False
        cgreg_result = False
        for idx in range(50):
            if not creg_result:
                (creg_result, creg_status_m) = self.command('AT+CREG?', 2, 'CREG: (0,[15])')
            if not cgreg_result:
                (cgreg_result, cgreg_status_m) = self.command('AT+CGREG?', 2, 'CGREG: (0,[15])')
            if creg_result and cgreg_result:
                break
            
        (csq_result, csq_status_m) = self.command('AT+CSQ', 5, 'CSQ:\s*(\d+),(\d+)')
        
        cpin_status = self.get_group(cpin_status_m,1)
        revision = self.get_group(gmr_status_m,1)
        (rssi, ber) = self.calc_rssi(csq_status_m)
        iccid = self.get_group(iccid_status_m,2)
        imei = self.get_group(imei_status_m,2)
        creg = self.get_group(creg_status_m,0)
        cgreg = self.get_group(cgreg_status_m,0)
        
        print ('PIN -> {r} {s}'.format(r=cpin_result, s=cpin_status))
        print ('GMR -> {r} {s}'.format(r=gmr_result, s=revision))
        print ('CSQ -> {r} {s} dBm'.format(r=csq_result, s=rssi))
        print ('CCID (ICCID) -> {r} {s}'.format(r=iccid_result, s=iccid))
        print ('GSN (IMEI) -> {r} {s}'.format(r=imei_result, s=imei))
        print ('CREG -> {r} {s}'.format(r=creg_result, s=creg))
        print ('CGREG -> {r} {s}'.format(r=cgreg_result, s=cgreg))
        
        self.command('ATD*99#')
        ppp = self.attachGSMtoPPP()
        return (iccid, imei, rssi, revision, ppp)

    def disconnect(self):
        press_modem_powerkey()
        pass