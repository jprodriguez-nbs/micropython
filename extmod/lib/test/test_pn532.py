import gc

gc.collect()
print(gc.mem_free())

import pn532.nfc as nfc
import pn532.interfaces as nfc_interfaces

import time
import binascii
import json
import esp32
import machine
import colors


import uasyncio as asyncio
import planter_pinout as PINOUT

import logging
from micropython import const
from machine import Pin, Timer
import utime


from pn532.interfaces.pn532i2c import Pn532I2c
from pn532.nfc.pn532 import Pn532_Generic

from pn532.nfc.llcp import Llcp
from pn532.nfc.snep import Snep


_logger = logging.getLogger("test")
_logger.setLevel(logging.DEBUG)

i2c = machine.SoftI2C(scl=machine.Pin(PINOUT.I2C_SCL), sda=machine.Pin(PINOUT.I2C_SDA),freq=400000)
r = i2c.scan()
_logger.debug("I2C SCAN: {r}".format(r=r))


class TestPn532i2cComm():
    def setUp(self):
        self.pn532 = Pn532I2c(i2c)
        self.pn532.begin()

    def test_getFirmware(self):
        self.pn532.writeCommand(bytearray([0x2]), bytearray())
        rsp = self.pn532.readResponse(10)
        print('Response {!r}'.format(rsp))
        #self.assertEqual(bytearray([0x32, 0x1, 0x6, 0x7]), rsp[1])    # Check against known firmware ver
        #self.assertEqual(4, rsp[0])    # Check length is correct
        
        if (rsp == (4,b'2\x01\x06\x07')):
            print ("Firmware version matches")
        else:
            print ("Firmware does not match")


class TestPn532Func():
    def setUp(self):
        # self.interface = pn532spi(pn532spi.SS0_GPIO8)
        self.interface = Pn532I2c(i2c)
        self.interface.begin()
        self.pn532 = Pn532_Generic(self.interface)

    def test_getFirmware(self):
        fw_ver = self.pn532.getFirmwareVersion()
        if (fw_ver != 0x32010607):
            print('Invalid fw version returned')

    def test_SAMConfig(self):
        ret = self.pn532.SAMConfig()
        if ret is not True:
            print('Failed to configure SAM')

    def test_readGPIO(self):
        gpio = self.pn532.readGPIO()
        print("gpio: {:#x}".format(gpio))

class TestPn532RFIDTags():

    def setUp(self):
        # self.interface = pn532spi(pn532spi.SS0_GPIO8)
        self.interface = Pn532I2c(i2c)
        self.interface.begin()
        self.pn532 = Pn532_Generic(self.interface)


    def setupNFC(self):
        self.setUp()

        versiondata = self.pn532.getFirmwareVersion()
        if not versiondata:
            print("Didn't find PN53x board")
            raise RuntimeError("Didn't find PN53x board")  # halt

        # Got ok data, print it out!
        print("Found chip PN5 {:#x} Firmware ver. {:d}.{:d}".format((versiondata >> 24) & 0xFF, (versiondata >> 16) & 0xFF,
                                                                    (versiondata >> 8) & 0xFF))

        # Set the max number of retry attempts to read from a card
        # This prevents us from waiting forever for a card, which is
        # the default behaviour of the pn532.
        self.pn532.setPassiveActivationRetries(0xFF)

        # configure board to read RFID tags
        self.pn532.SAMConfig()

    def cycle(self):
        print("Waiting for an ISO14443A card")

        # set shield to inListPassiveTarget
        success = self.pn532.inListPassiveTarget()

        if (success):

            print("Found something!")

            selectApdu = bytearray([0x00,                                     # CLA 
                                    0xA4,                                     # INS 
                                    0x04,                                     # P1  
                                    0x00,                                     # P2  
                                    0x07,                                     # Length of AID  
                                    0xF0, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, # AID defined on Android App 
                                    0x00 # Le
                                    ])

            success, response = self.pn532.inDataExchange(selectApdu)

            if (success):

                print("responseLength: {:d}", len(response))
                print(binascii.hexlify(response))

            while (success):
                apdu = bytearray(b"Hello from Arduino")
                success, back = self.pn532.inDataExchange(apdu)

                if (success):
                    print("responseLength: {:d}", len(back))
                    print(binascii.hexlify(back))
                else:
                    print("Broken connection?")
            else:
                print("Failed sending SELECT AID")
        else:
            print("Didn't find anything!")

        time.sleep(1)

    def cycle_ISO14443A(self):
        # Wait for an ISO14443A type cards (Mifare, etc.).  When one is found
        # 'uid' will be populated with the UID, and uidLength will indicate
        # if the uid is 4 bytes (Mifare Classic) or 7 bytes (Mifare Ultralight)
        success, uid = self.pn532.readPassiveTargetID(nfc.pn532.PN532_MIFARE_ISO14443A_106KBPS)

        if (success):
            print("Found a card!")
            print("UID Length: {:d}".format(len(uid)))
            print("UID Value: {}".format(binascii.hexlify(uid)))
            # Wait 1 second before continuing
            time.sleep(1)
            return True
        else:
            # pn532 probably timed out waiting for a card
            print("Timed out waiting for a card")
            return False

def exec_test():

    test = TestPn532i2cComm()
    test.setUp()
    test.test_getFirmware()
    
    
    test2 = TestPn532Func()
    test2.setUp()
    test2.test_getFirmware()
    test2.test_SAMConfig()
    test2.test_readGPIO()


    test3 = TestPn532RFIDTags()
    test3.setupNFC()
    while True:
        test3.cycle_ISO14443A()