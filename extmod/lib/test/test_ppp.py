import machine
import time
import umdc_pinout as PINOUT
from machine import UART, Pin

import socket
import utime
import sys
import network
import re


DETAILED_DEBUG = False

WDT_ENABLED = False
if WDT_ENABLED:
    _wdt = machine.WDT(timeout=240000)



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
    print('Test PPP - Setup modem UART {p} ...'.format(p=uart_port))

    gsm = machine.UART(uart_port, baudrate=baudrate, timeout=250, timeout_char=250, rx=modem_rx_pin, tx=modem_tx_pin)


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




def test_ppp(gsm=None):

    if gsm is None:
        gsm = get_uart()
    

    time.sleep(1)
    gsm.write("at\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)
    gsm.write("AT+CPIN?\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)
    #gsm.write("ate0\r\n")
    #print(gsm.readline())
    #print(gsm.readline())
    #time.sleep(1)
    gsm.write("AT+CREG?\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)

    # SIM operator name
    gsm.write("AT+COPS?\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)

    # Attach GPRS
    gsm.write("AT+CGATT?\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)

    gsm.write("AT+CNMI=0,0,0,0,0\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)
    gsm.write('AT+CGDCONT=1,"IP","'+PINOUT.APN+'"\r\n')
    print(gsm.readline())
    print(gsm.readline())

    # Check connection status
    gsm.write("AT+CGDCONT=?\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)

    # Check IP
    gsm.write("AT+CGPADDR=1\r\n")
    print(gsm.readline())
    print(gsm.readline())
    time.sleep(1)

    #time.sleep(1)
    #gsm.write('AT+CSTT="'+APN+'","'+PPP_USER+'","'+PPP_PSW+'"\r\n')
    #time.sleep(1)
    #print(gsm.readline())
    #print(gsm.readline())
    time.sleep(1)
    gsm.write('AT+CGDATA="PPP",1\r\n')
    
    for i in range(15):
        time.sleep(1)
        r = gsm.readline()
        if r:
            print(r)
            break
    
    import network

    print ("Create PPP")
    ppp=network.PPP(gsm)
    ppp.active(True)
    print ("Connect with authentication")
    ppp.connect(authmode=ppp.AUTH_CHAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
    print ("Wait for connected")
    for i in range(30):
        if ppp.isconnected() is False:
            time.sleep(1)
        else:
            break

    print(ppp.ifconfig())


interval = 1

class InitSimData():
    def __init__(self, gsm):
        if gsm is None:
            gsm = get_uart()
        self.gsm = gsm

    def start_1(self):
        time.sleep(1)
        time.sleep(interval)
        self.check_sim()
        time.sleep(interval)
        self.register_sim()

        # time.sleep(interval)
        # self.getOPR()

        time.sleep(interval)
        self.attachGPRS()

        time.sleep(interval)
        self.requestIPwithAPN()

        time.sleep(interval)
        self.getCGDCONT()

        time.sleep(interval)
        self.qosProfile()

        #time.sleep(interval)
        #self.qosProfilenext()


        time.sleep(interval)
        self.set_PDP_IP_ConectionAuthenticationType()

        time.sleep(interval)
        self.get_PDP_IP_ConectionAuthenticationType()

        time.sleep(interval)
        self.activateContext()


        time.sleep(interval)
        self.checkIP()

        time.sleep(interval)
        self.PDPcontext()

        time.sleep(interval)
        #self.switchToTransparentMode()

        time.sleep(interval)
        r = self.attachGSMtoPPP()
        return r


    def start_2(self):
        time.sleep(1)
        time.sleep(interval)
        self.sync()
        time.sleep(interval)
        
        self.set_functionality_level(0,0)
        time.sleep(interval)
        self.set_functionality_level(1,1)
        time.sleep(interval)
        self.check_sim()
        time.sleep(interval)
        
        self.set_functionality_level(0,0)
        time.sleep(interval)
        self.set_preferred_mode(2)
        time.sleep(interval)
        self.set_preferred_selection(3)
        time.sleep(interval)
        self.set_functionality_level(1,0)
        time.sleep(5)
        time.sleep(interval)

        #self.configPDP()
        self.configPDP(0, PINOUT.APN, PINOUT.PPP_USER, PINOUT.PPP_PSW)
        time.sleep(interval)
        
        ccid = self.getCCID()
        time.sleep(interval)
        
        swRevision = self.getSoftwareRevision()
        time.sleep(interval)
        
        imei = self.getIMEI()
        time.sleep(interval)
        
        rssi = self.getRSSI()
        time.sleep(interval)
        
        self.getPDPConfiguration()
        time.sleep(interval)
        
        self.configPDP(0, PINOUT.APN, PINOUT.PPP_USER, PINOUT.PPP_PSW)
        time.sleep(interval)
        
        self.getPDPConfiguration()
        time.sleep(interval)
        
        self.register_sim()
        time.sleep(interval)
        
        self.networkRegistrationStatus()
        time.sleep(interval)
        
        
        self.getAPN()
        time.sleep(interval)
         
        self.getUESystemInformation()
        time.sleep(interval)
        
        self.getOPR()
        time.sleep(interval)
        
        
        self.getECM_APN_Authentication()
        time.sleep(interval)
        
        
        self.getModel()
        time.sleep(interval)

        
        
        #self.requestIPwithSimbase(2)
        #time.sleep(interval)
        
        
        #self.requestIPwithSimbase(1)
        #time.sleep(interval)

        #self.register_sim_EPS()
        #time.sleep(interval)
        
        
        self.register_sim()
        time.sleep(interval)


        # time.sleep(interval)
        # self.getOPR()

        if False:
            time.sleep(interval)
            self.attachGPRS()

            time.sleep(interval)
            self.requestIPwithAPN()

            time.sleep(interval)
            self.getCGDCONT()

            time.sleep(interval)
            self.qosProfile()

            #time.sleep(interval)
            #self.qosProfilenext()


            time.sleep(interval)
            self.set_PDP_IP_ConectionAuthenticationType()

            time.sleep(interval)
            self.get_PDP_IP_ConectionAuthenticationType()

            time.sleep(interval)
            self.activateContext()


            time.sleep(interval)
            self.checkIP()

            time.sleep(interval)
            self.PDPcontext()

            time.sleep(interval)
            #self.switchToTransparentMode()

        else:
            
            self.configPDP(0, PINOUT.APN, PINOUT.PPP_USER, PINOUT.PPP_PSW)
            time.sleep(interval)
            
            time.sleep(interval)
            self.dial99()
            time.sleep(interval)

        time.sleep(interval)
        r = self.attachGSMtoPPP()
        return r
    
    def empty_buffer(self):
        # Empty buffer
        #return
        status = "Full"
        while status is not None and len(status)>0:
            status = self.gsm.readline()
            if status is not None:
                try:
                    status = status.decode().replace('\r\n','')
                    print(status)
                except:
                    pass
    

                
    
    def register_sim(self):
        while True:
            self.gsm.write("AT+CREG?\r\n")
            status = self.read_status()
            if status is not None and  (status == "+CREG: 0,1" or status == "+CREG: 0,5" ):
                print("Sim Registered with status",status)
                self.empty_buffer()
                return True
            else:
                pass
    
    def try_receive_TCP_data(self):
        while True:
            self.gsm.write("AT+CARECV?\r\n")
            status = self.read_status()
            if status is not None and "+CARECV:" in status:
                print("Received data: ",status)
                return True
            else:
                pass
    
    def register_sim_EPS(self):
        while True:
            self.gsm.write("AT+CEREG?\r\n")
            status = self.read_status()
            if status is not None and (status == "+CEREG: 0,1" or status == "+CEREG: 0,5" or status == "+CEREG: 0,4" ):
                print("Sim Registered EPS with status",status)
                self.empty_buffer()
                return True
            else:
                pass
    
    def check_sim(self):
        while True:
            self.gsm.write("AT+CPIN?\r\n")
            status = self.read_status()
            if status is not None and '+CPIN' in status:
                print("Sim status ",status)
                return True
            else:
                pass
            
            
    def sync(self):
        idx = 0
        while True:
            self.gsm.write("AT\r\n")
            status = self.read_status()
            if status is not None and status == "OK":
                print("Sim Initialized with status",status)
                return True

            idx = idx + 1
                
            if idx > 10:
                idx = 0
                press_modem_powerkey()
                utime.sleep(5)
    
    def set_functionality_level(self,level,reset=0):
        while True:
            self.gsm.write("AT+CFUN={l},{r}\r\n".format(l=level, r=reset))
            status = self.read_status()
            if status is not None and '+CFUN' in status:
                print("Functionality status ",status)
                return True
            else:
                pass
    
    def set_preferred_mode(self,mode=2):
        while True:
            # 2 = Auto
            self.gsm.write("AT+CNMP={m}\r\n".format(m=mode))
            status = self.read_status()
            if status is not None and '+CNMP' in status:
                print("Preferred mode ",status)
                return True
            else:
                pass
 
    def set_preferred_selection(self,mode=3):
        while True:
            # 3 = CAT-M and NB-IoT
            self.gsm.write("AT+CMNB={m}\r\n".format(m=mode))
            status = self.read_status()
            if status is not None and '+CMNB' in status:
                print("Preferred selection ",status)
                return True
            else:
                pass
    
    def getOPR(self):
        while True:
            self.gsm.write("AT+COPS?\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+COPS'):
                print("Sim Operator Name is",status)
                return True
            else:
                pass
            
    def getCCID(self):
        while True:
            self.gsm.write("AT+CCID\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+CCID'):
                status = self.read_first()
                parts = status.split('\r\n')
                if len(parts)>1:
                    iccid = parts[0]
                else:
                    iccid = status
                print("{s} -> CCID: {iccid}".format(s=status, iccid=iccid))
                self.empty_buffer()
                return iccid
            else:
                pass

    def getSoftwareRevision(self):
        while True:
            self.gsm.write("AT+GMR\r\n")
            status = self.read_first()
            if status is not None and status.startswith('Revision'):
                parts = status.split(':')
                if len(parts)>1:
                    revision = parts[1]
                else:
                    revision = status
                print("Software revision: ",revision)
                self.empty_buffer()
                return revision
            else:
                pass

    def getIMEI(self):
        while True:
            self.gsm.write("AT+GSN\r\n")
            status = self.read_status()
            if status is not None:
                if '+GSN' in status:
                    status = self.read_status()
                imei = status
                print("IMEI: ",imei)
                self.empty_buffer()
                return imei
            else:
                pass

    def getModel(self):
        while True:
            self.gsm.write("AT+GMM\r\n")
            status = self.read_first()
            if status is not None:
                model = status
                print("Model: ",model)
                self.empty_buffer()
                return model
            else:
                pass

    def dial99(self):
        while True:
            self.gsm.write("ATD*99#\r\n")
            status = self.read_first()
            if status is not None and 'CONNECT' in status:
                print(status)
                return status
            else:
                pass

    def getRSSI(self):
        rssi = None
        ber = None
        while True:
            self.gsm.write("AT+CSQ\r\n")
            status = self.read_first()
            if status is not None:
                if 'CSQ' in status:
                    status = self.read_status()
                    print("Signal quality: ",status)
                    re_csq_pattern = '.*\s(\d*),(\d*)'
                    re_csq = re.compile(re_csq_pattern)
                    m = re_csq.match(status)
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
                    return rssi
                else:
                    print(status)
            else:
                pass

    def getAPPNetworkActive(self):
        while True:
            self.gsm.write("AT+CNACT?\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+CNACT'):
                print("APP Network active: ",status)
                return True
            else:
                pass

    def setTCPUDPIdentifier(self,id=0):
        while True:
            self.gsm.write("AT+CACID={id}\r\n".format(id=id))
            status = self.read_first()
            if status is not None:
                print("TCP/UDP Identifier set to {id}: {s}".format(id=id,s=status))
                return True
            else:
                pass

    def defineSSL(self,cid=0, supportSSL=0):
        while True:
            m="AT+CASSLCFG={cid},SSL,{supportSSL}\r\n".format(cid=cid, supportSSL=supportSSL)
            self.gsm.write(m)
            status = self.read_first()
            if status is not None:
                print("SSL set to {m}: {s}".format(m=m,s=status))
                return True
            else:
                pass

    def openTCPConnection(self, cid=0, pdp_idx=0, server='', port=0):
        while True:
            m='AT+CAOPEN={cid},{pdp_idx},"TCP","{server}",{port}\r\n'.format(cid=cid, pdp_idx=pdp_idx, server=server, port=port)
            self.gsm.write(m)
            status = self.read_first()
            if status is not None:
                print("TCP Connection {m} result: {s}".format(m=m,s=status))
                return True
            else:
                pass

    def enableApp(self):
        while True:
            self.gsm.write("AT+CNACT=0,1\r\n")
            status = self.read_first()
            if status is not None:
                print("Enable APP witn CNACT : ",status)
                return True
            else:
                pass

    def getAPN(self):
        while True:
            self.gsm.write("AT+CGNAPN\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+CGNAPN'):
                print("Network APN in CAT-M or NB-IOT: ",status)
                return True
            else:
                pass
            
    def getPDPConfiguration(self):
        while True:
            self.gsm.write("AT+CNCFG?\r\n")
            status = self.read_first()
            if status is not None:
                if status.startswith('+CNCFG:'):
                    print("PDP Configuration: ",status)                
                    return True
                else:
                    print(status)
            else:
                pass
            
    def getECM_APN_Authentication(self):
        while True:
            self.gsm.write("AT+SECMAUTH?\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+SECMAUTH'):
                print("ECM APN and Authentication: ",status)
                return True
            else:
                pass   
            
    def enableECMAutoConnecting(self):
        while True:
            self.gsm.write("AT+SECMEN=1\r\n")
            status = self.read_first()
            if status is not None:
                print("Enable ECM Auto Connecting result: ",status)
                return True
            else:
                pass

    def getUESystemInformation(self):
        while True:
            self.gsm.write("AAT+CPSI?\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+CPSI'):
                print("UE System Information: ",status)
                return True
            else:
                pass

    def getGPRSStatus(self):
        while True:
            self.gsm.write("AT+CGATT?\r\n")
            status = self.read_first()
            if status is not None and status.startswith('+CGATT:'):
                print("GPRS Status ", status)
                return True
            else:
                pass

    def attachGPRS(self):
        idx = 0
        while True:
            if idx == 0:
                self.gsm.write("AT+CGATT=1\r\n")
                status = self.read_first()
                
            if idx == 1:
                self.gsm.write("AT+CGATT?\r\n")
                print("GPRS Status")
            idx = idx + 1
            if idx>25:
                idx = 0
            status = self.read_first()            
            if status == "+CGATT: 1":
                print("GPRS Attached with status ", status)
                return True
            else:
                #time.sleep(1)
                utime.sleep_ms(200)
                pass
    
    
    def requestIPwithSimbase(self,context):
        idx = 0
        while True:
            if idx == 0:
                if context == 1:
                    self.gsm.write('AT+CGDCONT=1,"IP","simbase"\r\n')
                if context == 2:
                    self.gsm.write('AT+CGDCONT=2,"IP","simbase","0.0.0.0",0,0,0,0\r\n')
            idx = idx + 1
            if idx>25:
                idx = 0
            status = self.read_status()
            if status is not None:
                print("Checking status for CDGCONT response--",status)
            if status is not None and '+CGDCONT' in status:
                print("Sim Connected with APN and IP Address is ", status)
                return status
            else:
                utime.sleep_ms(200)
                pass
            
          
    def configPDP(self, cid=0, apn="simbase",user=None,psw=None):
        idx = 0
        while True:
            if idx == 0:
                u = ',"{u}"'.format(u=user) if user else ''
                p = ',"{p},3"'.format(p=psw) if user else ''
                m = 'AT+CNCFG={cid},0,"{apn}"{user}{psw}\r\n'.format(
                    cid=cid,
                    apn=apn, user=u, psw=p
                )
                print("Config PDP with {m}".format(m=m))
                self.gsm.write(m)
            idx = idx + 1
            if idx>25:
                idx = 0
            status = self.read_status()
            if status is not None:
                print("Checking status for CNCFG response--",status)
                return status
            else:
                utime.sleep_ms(200)
                pass
            
    
    def requestIPwithAPN(self):
        idx = 0
        while True:
            if idx == 0:
                self.gsm.write('AT+CGDCONT=1,"IP","'+PINOUT.APN+'",\r\n')
            idx = idx + 1
            if idx>25:
                idx = 0
            status = self.read_status()
            if status is not None:
                print("Checking status for CDGCONT response--",status)
            if status is not None and '+CGDCONT' in status:
                print("Sim Connected with APN and IP Address is ", status)
                return status
            else:
                utime.sleep_ms(200)
                pass
            

    def getCGDCONT(self):
        
        status = None
        while status is None or status.startswith('+CGDCONT') is False:
            self.gsm.write('AT+CGDCONT=?\r\n')
            status = self.read_first()
            print("IP Details--",status)
            if status is not None and  status.startswith('+CGDCONT'):
                print("Sim Connected with IP---- ", status)
                return status
            else:
                time.sleep(1)
                

    def getCGDCONTsec(self):
        
        status = ''
        while status == '':
            self.gsm.write('AT+CGDCONT=?\r\n')
            status = self.read_status()
            print("IP Sec st Details--",status)
            if not status == '':
                print("Sim sec st Connected with IP---- ", status)
                return status
            else:
                time.sleep(1)
                #self.getCGDCONT()


    def activateContext(self):
        
        status = None
        while status is None or status.startswith('OK') is False:
            self.gsm.write('AT+CGACT=1,1\r\n')
            status = self.read_first()
            print("Context activation--",status)
            if  status is not None and status.startswith('OK'):
                print("Context activated---- ", status)
                return status
            else:
                time.sleep(1)

    def networkRegistrationStatus(self):
        while True:
            self.gsm.write("AT+CGREG?\r\n")
            status = self.read_status()
            if status == "+CGREG: 0,1" or status == "+CGREG: 0,5" :
                print("Network registration status ",status)
                self.empty_buffer()
                return True
            else:
                pass
            
            
    def set_PDP_IP_ConectionAuthenticationType(self):
        idx = 0
        while True:
            if idx == 0:
                msg = "AT+CGAUTH=1,3,{psw},{user}\r\n".format(psw=PINOUT.PPP_PSW, user=PINOUT.PPP_USER)
                self.gsm.write(msg)
            idx = idx + 1
            if idx>5: idx = 0
            status = self.read_status()
            if status == "OK":
                print("PDP_IP_ConectionAuthenticationType set: ",status)
                return True
            else:
                pass

    def get_PDP_IP_ConectionAuthenticationType(self):
        idx = 0        
        while True:
            if idx == 0:
                msg = "AT+CGAUTH?\r\n".format()
                self.gsm.write(msg)
            idx = idx + 1
            if idx>5: idx = 0
            status = self.read_status()
            if  status is not None and status.startswith('+CGAUTH'):
                print("PDP_IP_ConectionAuthenticationType : ",status)
                return True
            else:
                pass

    def qosProfile(self):
        """Define a QoS profile for PDP context 1, with
        Traffic Class 3 (background), maximum bit rate
        64 kb/s both for UL and for DL, no Delivery Order
        requirements, a maximum SDU size of 320
        octets, an SDU error ratio of 10-4
        , a residual bit
        error ratio of 10-5
        , delivery of erroneous SDUs
        allowed and Traffic Handling Priority 3."""

        status = ''
        while status == '':
            self.gsm.write('AT+CGEQREQ=1,3,64,64,,,0,320,"1E4","1E5",1,,3\r\n')
            status = self.read_first()
            print("Qos Profile",status)
            if not status== '':
                print("Sim QOS Status---- ", status)
                return status
            else:
                time.sleep(1)
                #self.qosProfile()

    def PDPcontext(self):
        """PDP context 1 activation (alternatively with
            AT+CGDATA="PPP", 1 or ATD*99***1#)."""

        self.empty_buffer()

        li_cmd = ['AT+CGDATA="PPP",1\r\n', 'ATD*99***1#\r\n']
        cmd_idx = 1
        status = None
        while status is None or status.startswith('CONNECT') is False:
            cmd = li_cmd[cmd_idx]
            self.gsm.write(cmd)
            status = self.read_first()
            print("CGDDATA PP ATTACHED ----", status)
            if  status is not None and status.startswith('CONNECT'):
                print("CGDDATA context 1 activation---- ", status)
                return status
            else:
                cmd_idx = 1 - cmd_idx
                time.sleep(1)


    def checkIP(self):
        """Show address of PDP context 1. If PPP is used
            this command shall be sent from another AT
            command interface."""
        status = None
        self.empty_buffer()
        idx = 0
        while True:
            if idx == 0:
                self.gsm.write('AT+CGPADDR=1\r\n')
            idx = idx + 1
            if idx>5: idx = 0
            status = self.read_first()
            if status is not None and len(status):
                print("checkip method --",status)
            if status.startswith('+CGPADDR'):
                print("PDP context 1 activation---- ", status)
                return status
            else:
                time.sleep(1)
                #self.checkIP()

            
    def switchToTransparentMode(self):
        idx = 0
        while True:
            if idx == 0:
                msg = "AT+CASWITCH==1,1\r\n"
                self.gsm.write(msg)
            idx = idx + 1
            if idx>5: idx = 0
            status = self.read_status()
            if  status is not None and status.startswith('+CASWITCH'):
                print("switchToTransparentMode: ",status)
                return True
            else:
                pass

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
            time.sleep(1)
            print("Check if network.PPP is connected")
            
            idx = 0
            while is_connected is False and idx < 100:            
                idx = idx + 1
                if GPRS.isconnected():
                    print(GPRS.ifconfig())
                    is_connected = True
                else:
                    time.sleep(0.5)
                    #self.attachGSMtoPPP()

            if is_connected is False:
                GPRS.active(False)
                time.sleep(1)
                del GPRS
                GPRS = None

        return GPRS


    def read_status(self):
        status = self.gsm.readline()
        if status is not None:
            print(str(status))
        if status is None or len(status)==0:
            status = self.gsm.readline()
            if status is not None:
                print(str(status))
        if status:
            try:
                status = status.decode().replace('\r\n','')
            except Exception as ex:
                status = None
            return status
        else:
            #print("Sim Module Not Connected or UART used by other device")
            pass


    def read_first(self):
        status = self.gsm.readline()
        if status:
            try:
                status = status.decode().replace('\r\n','')
            except Exception as ex:
                status = None
            return status
        else:
            #print("Sim Module Not Connected or UART used by other device")
            pass





    def receive(self):
        x = self.gsm.read()
        if x is not None:
            print('Received: {}\n'.format(x))
        return x

    def send(self,data):
        print('Send: {}'.format(data))
        self.gsm.write(data)
        time.sleep(0.3)

    def demo(self):
        pp = 0
        pp_2 = 0
        while True:
            if pp == 0:
                self.send('AT')
                x = self.receive()
                if x is not None:
                    if 'AT' in x:
                        pp += 1
                        pp_2 = 0
            elif pp == 1:
                cmds = ['ATE0', 'ATI\r\n', 'AT+CPIN?\r\n', 'AT+CREG=0\r\n', 'AT+CGREG=0\r\n']
                self.send(cmds[pp_2])
                x = self.receive()
                if x is not None:
                    pp_2 += 1
                if pp_2 == len(cmds):
                    pp += 1
                    pp_2 = 0
            elif pp == 2:
                self.send("AT+CREG?\r\n")
                x = self.receive()
                if x is not None:
                    if ('+CREG: 0,5' in x) or ('+CREG: 0,1' in x):
                        pp += 1
                        pp_2 = 0
            elif pp == 3:
                self.send("AT+CGREG?\r\n")
                x = self.receive()
                if x is not None:
                    if ('+CGREG: 0,5' in x) or ('+CGREG: 0,1' in x):
                        pp += 1
                        pp_2 = 0
            elif pp == 4:
                cmds = ['AT+COPS?\r\n', 'AT+CSQ\r\n',
                        #'AT+CNMI=0,0,0,0,0\r\n',
                        'AT+QICSGP=1,1,\"clnxpt.vf.global\",\"\",\"\",0\r\n', #'AT+CGDATA=?\r\n',
                        #'AT+CGDATA="PPP",1',
                        'ATD*99#\r\n'
                        ]
                self.send(cmds[pp_2])
                x = self.receive()
                if x is not None:
                    pp_2 += 1
                if pp_2 == len(cmds):
                    pp += 1
                    pp_2 = 0
            elif pp == 5:
                import network
                print('Start PPP')
                ppp = network.PPP(self.gsm)
                ppp.active(True)
                ppp.connect()
                i = 0
                while i < 30:
                    time.sleep(1)
                    i += 1
                    if ppp.isconnected():
                        print(ppp.ifconfig())
                        pp += 1
                        break
            elif pp == 6:
                print('Try to send something.')
                i = 0
                exitwhile = False
                while not exitwhile:
                    s = None
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(3)
                        s.connect(('-----ip-----', 5555))
                        s.send('Hello world! ({})\n'.format(i))
                        i += 1
                        t = 5
                        data = ''
                        while t > 0:
                            time.sleep(1)
                            t -= 1
                            s.setblocking(0)
                            try:
                                data = s.recv(1024)
                            except:
                                pass
                            if len(data) > 0:
                                exitwhile = True
                                t = -1
                                print('Received: {}\n'.format(data.decode('utf-8')))
                                break
                    except Exception as ex:
                        print(ex)
                    if s is not None:
                        s.close()
                    time.sleep(1)
                pp += 1
            elif pp == 7:
                print('bye bye')
                pp += 1
            elif pp == 8:
                pass
            #time.sleep(1)