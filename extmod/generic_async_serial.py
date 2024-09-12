#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

from machine import UART
from machine import Pin
import struct
import time
import machine
import uasyncio as asyncio
from time_it import asynctimeit, timed_function

class GenericAsyncSerial:

    def __init__(self, uart_id, baudrate=9600, data_bits=8, stop_bits=1, parity=None, pins=None, ctrl_pin=None, tx_pin=None, rx_pin=None):
        if tx_pin is not None and rx_pin is not None:
            self._uart = UART(uart_id, baudrate=baudrate, tx=tx_pin, rx=rx_pin)
            self._uart.init(baudrate=baudrate, bits=data_bits, parity=parity, stop=stop_bits)
        else:
            self._uart = UART(uart_id, baudrate=baudrate, bits=data_bits, parity=parity, \
                            stop=stop_bits, timeout_chars=2, pins=pins)
        
        self.swriter = asyncio.StreamWriter(self._uart, {})
        self.sreader = asyncio.StreamReader(self._uart)
        
        if ctrl_pin is not None:
            self._ctrlPin = Pin(ctrl_pin, mode=Pin.OUT)
        else:
            self._ctrlPin = None

        if baudrate <= 19200:
            self._t35chars = (3500000 * (data_bits + stop_bits + 2)) // baudrate
        else:
            self._t35chars = 1750


    def __del__(self):
        # This method is to delete the asyncserial object releasing the uart bus and pins
        del self.swriter
        del self.sreader
        self.swriter = None
        self.sreader = None
        self._uart.deinit()
        del self._uart
        self._uart = None


    def _bytes_to_bool(self, byte_list):
        bool_list = []
        for index, byte in enumerate(byte_list):
            bool_list.extend([bool(byte & (1 << n)) for n in range(8)])

        return bool_list

    def _to_short(self, byte_array, signed=True):
        response_quantity = int(len(byte_array) / 2)
        fmt = '>' + (('h' if signed else 'H') * response_quantity)

        return struct.unpack(fmt, byte_array)

    def _exit_read(self, response):
        #l = len(response)
        # Look for end-of-line
        if response[-1] == '\n':
            return True
        else:
            return False


    @staticmethod
    #@asynctimeit
    async def _uart_read_and_extend(sreader, response):
        #response.extend(await sreader.read())
        b = await sreader.read(-1)
        response.extend(b)


    #@asynctimeit
    async def _uart_flush_rx_fifo(self):
        try:
            await asyncio.wait_for(self.sreader.read(-1), timeout = 0.001)
        except asyncio.TimeoutError:
            pass

    #@asynctimeit
    async def _uart_read(self):
        response = bytearray()

        for x in range(1, 1024):
            #if self._uart.any():
            try:
                await asyncio.wait_for(AsyncSerial._uart_read_and_extend(self.sreader, response), timeout = 0.05)
                # variable length function codes may require multiple reads
                if self._exit_read(response):
                    break
            except asyncio.TimeoutError:
                pass

        return response

    async def _uart_read_frame(self, timeout=None):
        bytes = bytearray()

        start_ms = time.ticks_ms()
        while timeout == None or time.ticks_diff(start_ms, time.ticks_ms()) <= timeout:
            last_byte_ts = time.ticks_us()
            while time.ticks_diff(last_byte_ts, time.ticks_us()) <= self._t35chars:
                #r = self._uart.readall()
                r = await self._uart_read()
                if r != None:
                    bytes.extend(r)
                    last_byte_ts = time.ticks_us()

            if len(bytes) > 0:
                return bytes

        return bytes


    #@asynctimeit
    async def _send(self, data):
        serial_pdu = bytearray()
        serial_pdu.append(data)

        if self._ctrlPin:
            self._ctrlPin(1)

        #self._uart.write(serial_pdu)
        await self.swriter.awrite(serial_pdu)

        if self._ctrlPin:
            while not self._uart.wait_tx_done(2):
                machine.idle()
            time.sleep_us(self._t35chars)
            self._ctrlPin(0)

    
    async def _send_receive(self, data):
        # flush the Rx FIFO
        await self._uart_flush_rx_fifo()
        await self._send(data)
        response = await self._uart_read()
        return self._validate_resp_hdr(response)

    def _validate_resp_hdr(self, response):

        if len(response) == 0:
            raise OSError('no data received from slave')

        if (response[-1] != '\n'):
            raise ValueError('Received data does not end with EOL')

        return response

    async def send_receive(self, data):
        resp_data = await self._send_receive(data)
        return resp_data

    async def send(self, data):
        await self._uart_flush_rx_fifo()
        await self._send(data)

    async def read(self):
        response = await self._uart_read()
        return self._validate_resp_hdr(response)
