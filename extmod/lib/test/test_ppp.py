import machine
import time
import planter_pinout as PINOUT
from machine import UART, Pin

import socket
import utime

import planter.config as CFG

#_apn = "movistar.es"
#_ppp_user = "movistar"
#_ppp_password = "movistar"

CFG.init()
_apn = None
_ppp_user = None
_ppp_password = None
try:
    _apn = CFG.config()[CFG.K_GPRS][CFG.K_APN]
    _ppp_user = CFG.config()[CFG.K_GPRS][CFG.K_USER]
    _ppp_password = CFG.config()[CFG.K_GPRS][CFG.K_PSW]
except Exception as ex:
    print("Failed to get PPP configuration")
    _apn = "movistar.es"
    _ppp_user = "movistar"
    _ppp_password = "movistar"
    

def get_uart():
    MODEM_PWKEY_PIN_OBJ = Pin(PINOUT.MODEM_PWKEY_PIN, Pin.OUT)
    MODEM_RST_PIN_OBJ = Pin(PINOUT.MODEM_RST_PIN, Pin.OUT)
    MODEM_POWER_ON_PIN_OBJ = Pin(PINOUT.MODEM_POWER_ON_PIN, Pin.OUT)

    #MODEM_PWKEY_PIN_OBJ.value(0)
    #MODEM_RST_PIN_OBJ.value(1)
    #MODEM_POWER_ON_PIN_OBJ.value(1)

    # Prepare
    MODEM_RST_PIN_OBJ.value(1)
    MODEM_PWKEY_PIN_OBJ.value(0)

    # Power ON
    MODEM_POWER_ON_PIN_OBJ.value(0)
    utime.sleep_ms(700)


    # POWER KEY
    MODEM_PWKEY_PIN_OBJ.value(1)
    utime.sleep_ms(1200)

    MODEM_PWKEY_PIN_OBJ.value(0)
    utime.sleep_ms(1800)   

    MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None)

    #gsm = machine.UART(1,tx=PINOUT.MODEM_TX_PIN, rx=PINOUT.MODEM_RX_PIN, timeout=1000,  baudrate=9600)
    gsm = UART(1, 115200, timeout=1000, rx=PINOUT.MODEM_RX_PIN, tx=PINOUT.MODEM_TX_PIN)
    return gsm

def test_ppp():

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
    gsm.write('AT+CGDCONT=1,"IP","'+_apn+'"\r\n')
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
    #gsm.write('AT+CSTT="'+_apn+'","'+_ppp_user+'","'+_ppp_password+'"\r\n')
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
    ppp.connect(authmode=ppp.AUTH_CHAP, username=_ppp_user, password=_ppp_password)
    print ("Wait for connected")
    for i in range(30):
        if ppp.isconnected() is False:
            time.sleep(1)
        else:
            break

    print(ppp.ifconfig())


interval = 1

class InitSimData():
    def __init__(self):
        self.gsm = get_uart()

    def start(self):
        time.sleep(interval)
        self.check_sim()
        time.sleep(interval)
        self.register_sim()

        # time.sleep(interval)
        # self.getOPR()

        time.sleep(interval)
        self.attachGPRS()

        time.sleep(interval)
        self.rquestIPwithAPN()

        time.sleep(interval)
        self.getCGDCONT()

        # time.sleep(interval)
        # self.qosProfile()

        # time.sleep(interval)
        # self.qosProfilenext()


        time.sleep(interval)
        self.checkIP()

        time.sleep(interval)
        self.PDPcontext()


        time.sleep(interval)
        r = self.attachGSMtoPPP()
        return r

    
    def check_sim(self):
        while True:
            self.gsm.write("AT\r\n")
            status = self.read_status()
            if status == "OK":
                print("Sim Initialized with status with status",status)
                return True
            else:
                pass
    
    def register_sim(self):
        while True:
            self.gsm.write("AT+CREG?\r\n")
            status = self.read_status()
            if status == "+CREG: 0,1":
                print("Sim Registered with status with status",status)
                return True
            else:
                pass
    
    def getOPR(self):
        while True:
            self.gsm.write("AT+COPS?\r\n")
            status = self.read_first()
            if status.startswith('+COPS'):
                print("Sim Operator Name is",status)
                return True
            else:
                pass

    def attachGPRS(self):
        while True:
            self.gsm.write("AT+CGATT?\r\n")
            status = self.read_first()
            print("GPRS Status")
            if status == "+CGATT: 1":
                print("GPRS Attached with status with status", status)
                return True
            else:
                pass
    
    def rquestIPwithAPN(self):
        self.gsm.write('AT+CGDCONT=1,"IP","'+_apn+'",\r\n')
        status = self.read_status()
        print("Checking status for CDGCONT response--",status)
        if status == 'OK':
            print("Sim Connected with _apn and IP Address is ", status)
            return status
        else:
            self.rquestIPwithAPN()

    def getCGDCONT(self):
        self.gsm.write('AT+CGDCONT=?\r\n')
        status = self.read_first()
        print("IP Details--",status)
        if status.startswith('+CGDCONT'):
            print("Sim Connected with IP---- ", status)
            return status
        else:
            time.sleep(1)
            self.getCGDCONT()

    def getCGDCONTsec(self):
        self.gsm.write('AT+CGDCONT=?\r\n')
        status = self.read_status()
        print("IP Sec st Details--",status)
        if not status == '':
            print("Sim sec st Connected with IP---- ", status)
            return status
        else:
            time.sleep(1)
            self.getCGDCONT()

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

        self.gsm.write('AT+CGEQREQ=1,3,64,64,,,0,320,"1E4","1E5",1,,3\r\n')
        status = self.read_first()
        print("Qos Profile",status)
        if not status== '':
            print("Sim QOS Status---- ", status)
            return status
        else:
            time.sleep(1)
            self.qosProfile()

    def PDPcontext(self):
        """PDP context 1 activation (alternatively with
            AT+CGDATA="PPP", 1 or ATD*99***1#)."""

        self.gsm.write('AT+CGDATA="PPP",1\r\n')
        status = self.read_first()
        print("CGDDATA PP ATTACHED ----", status)
        if status.startswith('CONNECT'):
            print("CGDDATA context 1 activation---- ", status)
            return status
        else:
            time.sleep(1)
            self.PDPcontext()

    def checkIP(self):
        """Show address of PDP context 1. If PPP is used
            this command shall be sent from another AT
            command interface."""

        self.gsm.write('AT+CGPADDR=1\r\n')
        status = self.read_first()
        print("checkip method --",status)
        if status.startswith('+CGPADDR'):
            print("PDP context 1 activation---- ", status)
            return status
        else:
            time.sleep(1)
            self.checkIP()



    def attachGSMtoPPP(self):
        import network
        GPRS=network.PPP(self.gsm)
        GPRS.active(True)
        GPRS.connect(authmode=GPRS.AUTH_CHAP, username=_ppp_user, password=_ppp_password)
        if GPRS.isconnected():
            print(GPRS.ifconfig())
            return True
        else:
            time.sleep(0.5)
            self.attachGSMtoPPP()

        return GPRS


    def read_status(self):
        self.gsm.readline()
        status = self.gsm.readline()
        if status:
            status = status.decode().replace('\r\n','')
            return status
        else:
            print("Sim Module Not Connected or UART using by other device")

    def read_first(self):
        status = self.gsm.readline()
        if status:
            status = status.decode().replace('\r\n','')
            return status
        else:
            print("Sim Module Not Connected or UART using by other device")



uart = get_uart()

def receive():
    x = uart.read()
    if x is not None:
        print('Received: {}\n'.format(x))
    return x

def send(data):
    print('Send: {}'.format(data))
    uart.write(data)
    time.sleep(0.3)

def demo():
    pp = 0
    pp_2 = 0
    while True:
        if pp == 0:
            send('AT')
            x = receive()
            if x is not None:
                if 'AT' in x:
                    pp += 1
                    pp_2 = 0
        elif pp == 1:
            cmds = ['ATE0', 'ATI\r\n', 'AT+CPIN?\r\n', 'AT+CREG=0\r\n', 'AT+CGREG=0\r\n']
            send(cmds[pp_2])
            x = receive()
            if x is not None:
                pp_2 += 1
            if pp_2 == len(cmds):
                pp += 1
                pp_2 = 0
        elif pp == 2:
            send("AT+CREG?\r\n")
            x = receive()
            if x is not None:
                if ('+CREG: 0,5' in x) or ('+CREG: 0,1' in x):
                    pp += 1
                    pp_2 = 0
        elif pp == 3:
            send("AT+CGREG?\r\n")
            x = receive()
            if x is not None:
                if ('+CGREG: 0,5' in x) or ('+CGREG: 0,1' in x):
                    pp += 1
                    pp_2 = 0
        elif pp == 4:
            cmds = ['AT+COPS?\r\n', 'AT+CSQ\r\n',
                    #'AT+CNMI=0,0,0,0,0\r\n',
                    'AT+QICSGP=1,1,\"movistar.es\",\"\",\"\",0\r\n', #'AT+CGDATA=?\r\n',
                    #'AT+CGDATA="PPP",1',
                    'ATD*99#\r\n'
                    ]
            send(cmds[pp_2])
            x = receive()
            if x is not None:
                pp_2 += 1
            if pp_2 == len(cmds):
                pp += 1
                pp_2 = 0
        elif pp == 5:
            import network
            print('Start PPP')
            ppp = network.PPP(uart)
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