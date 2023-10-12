
import gc
import micropython
import machine
import tools
print("Raw PPP")
print (tools.free(True))


import time
import socket
import utime
import network
import gc
import re

import umdc_pinout as PINOUT




class raw_ppp(object):
    def __init__(self, uart=None):
        if uart is not None:
            self.uart = uart
            self.initialised=True
        else:

            #uart1 = UART(2, tx=17, rx=16, baudrate=115200, timeout=1000)
            print('RAW PPP - Setup modem UART {p} ...'.format(p=PINOUT.MODEM_UART_PORT))
            self.uart = machine.UART(PINOUT.MODEM_UART_PORT, rx=PINOUT.MODEM_RX_PIN, tx=PINOUT.MODEM_TX_PIN, baudrate=PINOUT.MODEM_BAUDRATE, timeout=3000)
            self.initialised=False

        self.ppp = None

    def initialise(self, forced=False):
        
        if self.initialised is False or forced:
            MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.OUT) if PINOUT.MODEM_PWKEY_PIN is not None else None
            MODEM_RST_PIN_OBJ = machine.Pin(PINOUT.MODEM_RST_PIN, machine.Pin.OUT) if PINOUT.MODEM_RST_PIN is not None else None
            MODEM_POWER_ON_PIN_OBJ = machine.Pin(PINOUT.MODEM_POWER_ON_PIN, machine.Pin.OUT) if PINOUT.MODEM_POWER_ON_PIN is not None else None

            #MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
            #MODEM_RST_PIN_OBJ.value(1)
            #MODEM_POWER_ON_PIN_OBJ.value(1)

            # Prepare
            if MODEM_RST_PIN_OBJ:
                MODEM_RST_PIN_OBJ.value(1)
                
            if MODEM_PWKEY_PIN_OBJ:
                print("r MODEM_PWKEY_PIN OFF -> {v}".format(v=PINOUT.MODEM_PWKEY_OFF))
                MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)

            # Power ON
            if MODEM_POWER_ON_PIN_OBJ:
                MODEM_POWER_ON_PIN_OBJ.value(1)
            utime.sleep_ms(700)


            # POWER KEY
            if MODEM_PWKEY_PIN_OBJ:
                print("MODEM_PWKEY_PIN ON -> {v}".format(v=PINOUT.MODEM_PWKEY_ON))
                MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_ON)
            utime.sleep_ms(1200)

            if MODEM_PWKEY_PIN_OBJ:
                print("r MODEM_PWKEY_PIN OFF -> {v}".format(v=PINOUT.MODEM_PWKEY_OFF))
                MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
            utime.sleep_ms(1800)   

            MODEM_PWKEY_PIN_OBJ = machine.Pin(PINOUT.MODEM_PWKEY_PIN, machine.Pin.IN, pull=None) if PINOUT.MODEM_PWKEY_PIN is not None else None

        self.initialised=True

    def receive_new(self, wait_time=3):
        ts_start = utime.time()
        elapsed = 0
        x = None
        #while (self.uart.any() == 0) and (elapsed < wait_time):
        while x is None and (elapsed < wait_time):
            utime.sleep_ms(100)
            ts_now = utime.time() 
            elapsed = ts_now - ts_start            
            x = self.uart.read()
            
        if x is not None:
            print('Received: {x} after {e} [s]\n'.format(x=x, e=elapsed))
        return x
    
    def receive(self, timeout=3):
        x = self.uart.read()
        if x is not None:
            print('Received: {}\n'.format(x))
        return x

    def send(self, data):
        print('Send: {}'.format(data))
        self.uart.write(data)
        time.sleep(0.3)



    def demo(self, connect_ppp=True):
        
        self.initialise()
        iccid = None
        rssi = None
        ber = None
        imei = None
        sw_release = None
        pp = 0
        pp_2 = 0
        nb_at = 0
        while True:
            if pp == 0:
                pp +=1
                continue
                self.send('AT')
                x = self.receive()
                if x is not None:
                    if 'AT' in x:
                        nb_at +=1
                        if nb_at >3:
                            pp += 1
                            pp_2 = 0
                            nb_at = 0
            elif pp == 1:
                
                #l=  ['echooff','modeminfo','checkpin','networkregistration','networkregistrationstatus','setfun','setfun','checkpin','setfun','setprefrerredmode','setprefrerredLTEmode','setfun']
                cmds = [
                    'ATE0', 
                    'ATI\r\n', 
                    'AT+CPIN?\r\n', 
                    'AT+CFUN=0\r\n',
                    'AT+CFUN?\r\n',
                    
                    #'AT+SECMAUTH?\r\n',
                    #"AT+SECMAUTH={apn},3,{u},{p}\r\n".format(apn=PINOUT.APN, u=PINOUT.PPP_USER, p=PINOUT.PPP_PSW),
                    #'AT+CGDCONT?\r\n',
                    'AT+CGDCONT=2,"IP","simbase","0.0.0.0",0,0,0,0',
                    'AT+CNCFG?\r\n',
                    "AT+CNCFG=0,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                    "AT+CNCFG=1,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                    "AT+CNCFG=2,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                    "AT+CNCFG=3,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                    "AT+CGAUTH=1,3,\"{u}\",\"{p}\"\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                    'AT+CREG=0\r\n', 
                    'AT+CGREG=0\r\n',
                    
                    
                    'AT+CNMP=2\r\n',
                    'AT+CMNB=3\r\n',
                    
                    'AT+CFUN=1,1\r\n',
                    'AT+CFUN?\r\n',
                    #'AT+CFUN=1,0\r\n',
                    
                    'AT+CPIN?\r\n',
                    
                    
                    'AT+CNCFG?\r\n',
                    'AT+CFUN=1\r\n',
                    'AT+CFUN?\r\n'
                    ]
                
                cmds = ['ATE0', 'ATI\r\n', 'AT+CPIN?\r\n', 
                        'AT+CGDCONT?\r\n',
                        "AT+CGDCONT=1,\"IP\",\"{apn}\",\"0.0.0.0\",0,0,0,0\r\n".format(apn=PINOUT.APN),
                        'AT+CNCFG?\r\n',
                        "AT+CNCFG=0,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW),
                        'AT+CREG=0\r\n', 'AT+CGREG=0\r\n','AT+CFUN=0\r\n','AT+CFUN=1,1\r\n','\AT+CPIN?\r\n','AT+CFUN=0\r\n','AT+CNMP=2\r\n','AT+CMNB=3\r\n','AT+CFUN=1\r\n']
                self.send(cmds[pp_2])
                time.sleep(1)
                x = self.receive(1)
                #if x is not None:
                a = cmds[pp_2].replace('\r','').replace('\n','')
                
                nb_at = nb_at + 1
                #if (x is not None and ('OK' in x or a in x)) or nb_at >12:
                if (x is not None) or nb_at >12:
                    nb_at = 0
                    pp_2 += 1
                    utime.sleep_ms(1000)
                if pp_2 == len(cmds):
                    nb_at = 0
                    pp += 1
                    pp_2 = 0
                
            
            elif pp == 2:
                # Get ICCID
                iccid = None
                self.send('AT+CCID\r\n')
                x = self.receive()
                if x is not None:
                    if iccid is None:
                        parts = x.decode().split('\r\n')
                        if len(parts)>1:
                            iccid = parts[1]
                    if ('OK' in x):
                        pp += 1
                        pp_2 = 0
            
            elif pp == 3:
                self.send("AT+CFUN?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1    
            
            elif pp == 4:
                # Software Release
                self.send("AT+GMR\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1  
                        nb_at = 0

            elif pp == 5:
                # IMEI
                self.send("AT+GSN\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'ERROR' in x:
                        pp += 1  
                        nb_at = 0
                else:
                    nb_at += 1
                    if nb_at > 5:
                        pp += 1  
                        nb_at = 0

            
            elif pp == 6:
                self.send("AT+CSQ\r\n")
                x = self.receive()
                if x is not None:
                    if 'CSQ' in x:
                        re_csq_pattern = 'CSQ:\s(\d*),(\d*)'
                        re_csq = re.compile(re_csq_pattern)
                        m = re_csq.match(x)
                        if m:
                            rssi_raw = int(m.groups(1))
                            ber = m.groups(2)
                            
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
                            
                    if 'OK' in x:
                        pp += 1      
            
                else:
                    nb_at += 1
                    if nb_at > 5:
                        pp +=1
                        rssi = None
            
            elif pp == 7:
                self.send("AT+CREG?\r\n")
                x = self.receive()
                if x is not None:
                    if ('+CREG: 0,5' in x) or ('+CREG: 0,1' in x) :
                        pp += 1
                        pp_2 = 0
            elif pp == 8:
                self.send("AT+CGREG?\r\n")
                x = self.receive()
                if x is not None:
                    if ('+CGREG: 0,5' in x) or ('+CGREG: 0,1' in x):
                        pp += 1

                
            elif pp == 9:
                self.send("AT+CGNAPN\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1       
            elif pp == 10:
                self.send("AT+CPSI?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1                

            elif pp == 11:
                #self.send("AT+SECMEN=?\r\n")
                #self.send("AT+CGATT?\r\n")
                self.send("AT+SECMEN=1\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1    
                        
            elif pp == 12:
                #self.send("AT+SECMEN?\r\n")
                self.send("AT+COPS?\r\n")
                #self.send("AT+SECMAUTH={apn},3,{u},{p}\r\n".format(apn=APN, u=PPP_USER, p=PPP_PSW))
                #self.send("AT+SECMAUTH={apn}\r\n".format(apn=APN))
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1    
                        
            elif pp == 13:
                #self.send("AT+SECMAUTH=?\r\n")
                self.send("AT+CGNAPN\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1                                   
                        
                        
            elif pp == 14:
                self.send("AT+SECMAUTH?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1        

            elif pp == 15:
                self.send("AT+CNCFG=?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1      
                 
            elif pp == 16:
                self.send("AT+CNCFG?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   


            elif pp == 17:
                self.send("AT+CNCFG=0,0,\"{apn}\",\"{u}\",\"{p}\",3\r\n".format(apn=PINOUT.APN,u=PINOUT.PPP_USER,p=PINOUT.PPP_PSW))
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   
                        
            elif pp == 18:
                self.send("AT+CNCFG?\r\n")
                
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   
                        
            elif pp == 19:
                # Model Identification
                self.send('AT+GMM\r\n')
                x = self.receive()
                if x is not None:
                    if ('OK' in x):
                        pp += 1
            elif pp == 20:
                pp +=1
                continue
                # Set USER
                self.send('AT+SAPBR=3,1,"USER","{user}"\r\n'.format(user=PINOUT.PPP_USER))
                x = self.receive()
                if x is not None:
                    if ('OK' in x):
                        pp += 1
            elif pp == 21:
                # Get ICCID
                iccid = None
                self.send('AT+CCID\r\n')
                x = self.receive()
                if x is not None:
                    if iccid is None:
                        parts = x.decode().split('\r\n')
                        if len(parts)>1:
                            iccid = parts[1]
                    if ('OK' in x):
                        pp += 1
                        pp_2 = 0
            elif pp == 22:
                cmds = ['AT+COPS?\r\n', 'AT+CSQ\r\n',
                        #'AT+CNMI=0,0,0,0,0\r\n',
                        #'AT+QICSGP=1,1,\"iot.1nce.net\",\"\",\"\",0\r\n', #'AT+CGDATA=?\r\n',
                        #'AT+CGDATA="PPP",1',
                        'ATD*99#\r\n'
                        #'ATD*99***1#\r\n'
                        #'AT+CNACT=0,1\r\n',
                        #'AT+CNACT?\r\n'
                        ]
                self.send(cmds[pp_2])
                x = self.receive()
                if x is not None:
                    pp_2 += 1
                if pp_2 == len(cmds):
                    pp += 1
                    pp_2 = 0
            
            elif pp == 23:
                
                pp +=1
                continue
                if True:
                    #self.send("ATO0\r\n")
                    self.send("AT+CASWITCH=1,1\r\n")
                    x = self.receive()
                    if x is not None:
                        if 'CONNECT' in x:
                            pp += 1  
                    else:
                        pp_2 +=1
                    if pp_2 > 4:
                        # Continue
                        pp +=1
                        pp_2=0 
                else:
                    self.send("AT+CREBOOT\r\n")
                    x = self.receive()
                    if x is not None:
                        if 'OK' in x:
                            pp += 1   

            elif pp == 24:
                if connect_ppp is False:
                    pp = pp + 1
                    break
                else:
                    print('Start PPP')
                    gc.collect()
                    print("Create network.PPP and activate")
                    self.ppp = network.PPP(self.uart)
                    self.ppp.active(True)
                    print("network.PPP.connect")
                    #self.ppp.connect(authmode=self.ppp.AUTH_CHAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
                    self.ppp.connect(authmode=self.ppp.AUTH_PAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
                    i = 0
                    while i < 60:
                        time.sleep(1)
                        i += 1
                        status = self.ppp.status()
                        config = self.ppp.ifconfig()
                        isconnected = self.ppp.isconnected()
                        print("PPP status {s}, config {c}, connected = {connected}".format(s=str(status), c=str(config), connected=str(isconnected)))
                        if self.ppp.isconnected():
                            print(self.ppp.ifconfig())
                            pp += 1
                            break
            elif pp == 25:
                pp +=1
                continue
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
            elif pp == 26:
                print('bye bye')
                pp += 1
            elif pp == 27:
                break
                pass
            #time.sleep(1)
            
            
        return (iccid, rssi, self.ppp)
            
            
    def raw_2(self):
        
        self.initialise()
        
        pp = 0
        pp_2 = 0
        nb_at = 0
        while True:
            if pp == 0:
                self.send('AT')
                x = self.receive()
                if x is not None:
                    if 'AT' in x:
                        nb_at +=1
                        if nb_at >3:
                            pp += 1
                            pp_2 = 0
            elif pp == 1:
                cmds = ['ATE0', 'ATI\r\n', 'AT+CPIN?\r\n', 'AT+CREG=0\r\n', 'AT+CGREG=0\r\n','AT+CFUN=0\r\n','AT+CFUN=1,1\r\n','\AT+CPIN?\r\n','AT+CFUN=0\r\n','AT+CNMP=2\r\n','AT+CMNB=3\r\n','AT+CFUN=1\r\n']
                self.send(cmds[pp_2])
                x = self.receive()
                if x is not None:
                    pp_2 += 1
                if pp_2 == len(cmds):
                    pp += 1
                    pp_2 = 0
            
            elif pp == 2:
                self.send("AT+CGDCONT=2,\"IP\",\"{apn}\",\"0.0.0.0\",0,0,0,0\r\n".format(apn=PINOUT.APN))
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'READY' in x or 'Ready' in x:
                        pp += 1    
            
            elif pp == 3:
                self.send("AT+CREG?\r\n")
                x = self.receive()
                if x is not None:
                    if ('+CREG: 0,5' in x) or ('+CREG: 0,1' in x) :
                        pp += 1
                        pp_2 = 0
            
            elif pp == 4:
                self.send("AT+CARECV?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1  

            elif pp == 5:
                self.send("AT+CSTATE?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'ERROR' in x:
                        pp += 1  
            
            elif pp == 6:
                self.send("AT+CGATT?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'ERROR' in x:
                        pp += 1  
            elif pp == 7:
                self.send("AT+CNACT?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'ERROR' in x:
                        pp += 1  

            elif pp == 8:
                pp +=1
                continue
                self.send("AT+CGDCONT=2,\"IP\",\"{apn}\"\r\n".format(apn=PINOUT.APN))
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1          
            elif pp == 9:
                self.send("AT+CGATT=1\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1       
            elif pp == 10:
                self.send("AT+CGNAPN\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1                

            elif pp == 11:
                self.send("AT+CNCFG=0,1,\"{apn}\"\r\n".format(apn=PINOUT.APN))
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1      
                        
            elif pp == 12:
                self.send("AT+CNACT=0,1\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1       
                        
            elif pp == 13:
                self.send("AT+CGATT?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1                                 
                        
                        
            elif pp == 14:
                self.send("AT+CNACT?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1        

            elif pp == 15:
                self.send("AT+CARECV?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1      
                 
            elif pp == 16:
                self.send("AT+CSTATE?\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x or 'ERROR' in x:
                        pp += 1   


            elif pp == 17:
                self.send("AT+CACID=0\r\n")
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   
                        
            elif pp == 18:
                self.send("AT+CASSLCFG=0,SSL,0\r\n")
                
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   
                        
            elif pp == 19:
                self.send("AT+CAOPEN=0,0,\"TCP\",\"{mqtt_broker}\",{mqtt_port}\r\n".format(mqtt_broker=PINOUT.MQTT_BROKER,mqtt_port=PINOUT.MQTT_PORT))
                x = self.receive()
                if x is not None:
                    if 'OK' in x:
                        pp += 1   
            elif pp == 20:
                self.send('AT+CASEND=0,21\r\n')
                x = self.receive()
                if x is not None:
                    if ('OK' in x):
                        pp += 1
                        pp_2 = 0
            elif pp == 21:
                self.send('AT+CARECV=0,4\r\n')
                x = self.receive()
                if x is not None:
                    if ('OK' in x):
                        pp += 1
                        pp_2 = 0
            elif pp == 22:
                pp +=1
                continue
                cmds = ['AT+COPS?\r\n', 'AT+CSQ\r\n',
                        #'AT+CNMI=0,0,0,0,0\r\n',
                        #'AT+QICSGP=1,1,\"iot.1nce.net\",\"\",\"\",0\r\n', #'AT+CGDATA=?\r\n',
                        #'AT+CGDATA="PPP",1',
                        'ATD*99#\r\n'
                        #'AT+CNACT=0,1\r\n',
                        #'AT+CNACT?\r\n'
                        ]
                self.send(cmds[pp_2])
                x = self.receive()
                if x is not None:
                    pp_2 += 1
                if pp_2 == len(cmds):
                    pp += 1
                    pp_2 = 0
            
            elif pp == 23:
                
                pp +=1
                continue
                if True:
                    #self.send("ATO0\r\n")
                    self.send("AT+CASWITCH=1,1\r\n")
                    x = self.receive()
                    if x is not None:
                        if 'CONNECT' in x:
                            pp += 1  
                    else:
                        pp_2 +=1
                    if pp_2 > 4:
                        # Continue
                        pp +=1
                        pp_2=0 
                else:
                    self.send("AT+CREBOOT\r\n")
                    x = self.receive()
                    if x is not None:
                        if 'OK' in x:
                            pp += 1   

            elif pp == 24:
                print('Start PPP')
                gc.collect()
                print("Create network.PPP and activate")
                self.ppp = network.PPP(self.uart)
                self.ppp.active(True)
                print("network.PPP.connect")
                #self.ppp.connect(authmode=self.ppp.AUTH_CHAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
                self.ppp.connect(authmode=self.ppp.AUTH_PAP, username=PINOUT.PPP_USER, password=PINOUT.PPP_PSW)
                i = 0
                while i < 60:
                    time.sleep(1)
                    i += 1
                    status = self.ppp.status()
                    config = self.ppp.ifconfig()
                    isconnected = self.ppp.isconnected()
                    print("PPP status {s}, config {c}, connected = {connected}".format(s=str(status), c=str(config), connected=str(isconnected)))
                    if self.ppp.isconnected():
                        print(self.ppp.ifconfig())
                        pp += 1
                        break
            elif pp == 25:
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
            elif pp == 26:
                print('bye bye')
                pp += 1
            elif pp == 27:
                pass
            #time.sleep(1)