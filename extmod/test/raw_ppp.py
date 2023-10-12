from machine import UART, Pin
import time
import socket
import utime

import planter_pinout as PINOUT

MODEM_PWKEY_PIN_OBJ = Pin(PINOUT.MODEM_PWKEY_PIN, Pin.OUT)
MODEM_RST_PIN_OBJ = Pin(PINOUT.MODEM_RST_PIN, Pin.OUT)
MODEM_POWER_ON_PIN_OBJ = Pin(PINOUT.MODEM_POWER_ON_PIN, Pin.OUT)

#MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
#MODEM_RST_PIN_OBJ.value(1)
#MODEM_POWER_ON_PIN_OBJ.value(1)

# Prepare
MODEM_RST_PIN_OBJ.value(1)
MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)

# Power ON
MODEM_POWER_ON_PIN_OBJ.value(1)
utime.sleep_ms(700)


# POWER KEY
MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_ON)
utime.sleep_ms(1200)

MODEM_PWKEY_PIN_OBJ.value(PINOUT.MODEM_PWKEY_OFF)
utime.sleep_ms(1800)   


#uart1 = UART(2, tx=17, rx=16, baudrate=115200, timeout=1000)
uart = UART(1, rx=PINOUT.MODEM_RX_PIN, tx=PINOUT.MODEM_TX_PIN, baudrate=115200, timeout=1000)

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
                    'AT+QICSGP=1,1,\"iot.1nce.net\",\"\",\"\",0\r\n', #'AT+CGDATA=?\r\n',
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