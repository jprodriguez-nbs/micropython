

from machine import Pin
import time
import umdc_pinout as pinout

# OE 0 -> Receive
# OE 1 -> Transmit

oe = Pin(pinout.RS485_DIR, Pin.OUT, value=0)
oe.value(pinout.RS485_DIR_TX)

from machine import UART
u = UART(pinout.RS485_UART, baudrate=pinout.RS485_BAUDRATE, tx=pinout.RS485_TXD, rx=pinout.RS485_RXD)
u.init(baudrate=pinout.RS485_BAUDRATE, bits=pinout.RS485_DATABITS, parity=pinout.RS485_PARITY, stop=pinout.RS485_STOPBIT)

while True:
    # Set RS485 transceiver direction to TX
    oe.value(pinout.RS485_DIR_TX)
    frame = 'hello\n' 
    u.write(frame)
    # Wait until the bytes have been transmitted
    frame_time = (1+pinout.RS485_DATABITS+pinout.RS485_STOPBIT)*len(frame)/pinout.RS485_BAUDRATE
    time.sleep(frame_time)
    
    # Set RS485 transceiver direction to RX
    oe.value(pinout.RS485_DIR_RX)
    
    for aux in range(20):
        if u.any():
            l = u.readline()
            print(l)
        time.sleep(0.1)

