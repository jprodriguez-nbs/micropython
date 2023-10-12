#!/usr/bin/env python
#
# Copyright (c) 2019, Pycom Limited.
#
# This software is licensed under the GNU GPL version 3 or any
# later version, with permitted additional terms. For more information
# see the Pycom Licence v1.0 document supplied with this file, or
# available at https://www.pycom.io/opensource/licensing
#

# https://github.com/micropython/micropython/issues/8867
# https://github.com/micropython/micropython/commit/db7682e02d3ffd3338f20effc9ad4735a48bf774

import uModBus.functions as functions
import uModBus.const as Const
from uModBus.common import Request
from uModBus.common import ModbusException
from machine import UART
from machine import Pin
import struct
import time
import machine
import uasyncio as asyncio
from time_it import asynctimeit, timed_function
import binascii

import colors

import logging
_logger = logging.getLogger("umodbus.async_serial")
_logger.setLevel(logging.DEBUG)

class AsyncSerial:

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

        self._id = uart_id
        self._debug = False
        self._read_async = True
        
        _logger.info("Built AsyncSerial(uart {id}, {br} bps, bits {db}, stop {sb}, parity {p}, pins {pins}, ctrl {ctrl_pin}, tx {tx_pin}, rx {rx_pin}), t35ch={t35ch} [ms]".format(
            id=uart_id, br=baudrate, db=data_bits, sb=stop_bits, p=parity, pins=pins, ctrl_pin=ctrl_pin, tx_pin=tx_pin, rx_pin=rx_pin,
            t35ch = self._t35chars
        ))

    def __del__(self):
        # This method is to delete the asyncserial object releasing the uart bus and pins
        del self.swriter
        del self.sreader
        self.swriter = None
        self.sreader = None
        self._uart.deinit()
        del self._uart
        self._uart = None


    def _calculate_crc16(self, data):
        crc = 0xFFFF

        for char in data:
            crc = (crc >> 8) ^ Const.CRC16_TABLE[((crc) ^ char) & 0xFF]

        return struct.pack('<H',crc)

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
        l = len(response)
        if response[1] >= Const.ERROR_BIAS:
            if l < Const.ERROR_RESP_LEN:
                return False
        elif (Const.READ_COILS <= response[1] <= Const.READ_INPUT_REGISTER):
            expected_len = Const.RESPONSE_HDR_LENGTH + 1 + response[2] + Const.CRC_LENGTH
            if l < expected_len:
                return False
        elif l < Const.FIXED_RESP_LEN:
            return False

        return True


    @property
    def debug(self):
        return self._debug
    
    @debug.setter
    def debug(self, value):
        self._debug = value

    @property
    def read_async(self):
        return self._read_async
    
    @read_async.setter
    def read_async(self, value):
        self._read_async = value

    # async
    def read_all(self, n):
        yield asyncio.core._io_queue.queue_read(self._uart)
        return self._uart.read(n)


    #@staticmethod
    #@asynctimeit
    async def _uart_read_and_extend(self, sreader, response):
        #response.extend(await sreader.read())
        #b = await sreader.read_all(-1)
        b = await self.read_all(-1)
        response.extend(b)


    #@asynctimeit
    async def _uart_flush_rx_fifo(self):
        try:
            #await asyncio.wait_for(self.sreader.read_all(-1), timeout = 0.001)
            await asyncio.wait_for(self.read_all(-1), timeout = 0.001)
        except asyncio.TimeoutError:
            pass

    #@asynctimeit
    async def _uart_read(self, outbound_pdu=None):
        response = bytearray()
        nopost = False
        start_ts = time.ticks_us()

        if self._read_async:
            for x in range(1, 40):
                #if self._uart.any():
                try:
                    if self._debug:
                        start_ts = time.ticks_us()                    
                    awaitable = self._uart_read_and_extend(self.sreader, response)
                    await asyncio.wait_for_ms(awaitable, timeout = 500)
                    # variable length function codes may require multiple reads
                    if self._exit_read(response):
                        if self._debug:
                            _logger.debug("AsyncSerial.uart_read - exit read because response: {r}".format(r=binascii.hexlify(response).decode()))
                        break
                except asyncio.TimeoutError:
                    if self._debug:
                        now_ts = time.ticks_us()
                        elapsed_us = (now_ts-start_ts)
                        detail = "" if outbound_pdu is None else " (sent {ba})".format(ba=binascii.hexlify(outbound_pdu).decode())
                        msg = "AsyncSerial.uart_read timeout. Elapsed {e} [us]{detail}".format(e=elapsed_us,detail=detail)   
                        if nopost:
                            print(msg)
                        else:                     
                            _logger.error(msg,nopost)
                        nopost = True
                    
                    pass

        else:
            for x in range(1, 40):
                if self._uart.any():
                    #response.extend(self._uart.readall())
                    response.extend(self._uart.read())
                    # variable length function codes may require multiple reads
                    if self._exit_read(response):
                        if self._debug:
                            _logger.debug("AsyncSerial.uart_read - exit read because response: {r}".format(r=binascii.hexlify(response).decode()))
                        break
                await asyncio.sleep_ms(50)

        return response

    async def _uart_read_frame(self, timeout=None):
        rec_bytes = bytearray()

        start_ms = time.ticks_ms()
        while timeout == None or time.ticks_diff(start_ms, time.ticks_ms()) <= timeout:
            last_byte_ts = time.ticks_us()
            while time.ticks_diff(last_byte_ts, time.ticks_us()) <= self._t35chars:
                #r = self._uart.readall()
                r = await self._uart_read()
                if r != None:
                    rec_bytes.extend(r)
                    last_byte_ts = time.ticks_us()

            if len(rec_bytes) > 0:
                if self._debug:
                    _logger.debug("UART {id} received {ba}".format(id=self._id, ba=binascii.hexlify(rec_bytes).decode()))
                return rec_bytes

        if self._debug:
            _logger.debug("UART {id} received {ba}".format(id=self._id, ba=binascii.hexlify(rec_bytes).decode()))

        return rec_bytes

    #@asynctimeit
    async def _send_raw(self, serial_pdu):
        if self._ctrlPin:
            self._ctrlPin(1)

        #self._uart.write(serial_pdu)
        await self.swriter.awrite(serial_pdu)

        if self._ctrlPin:
            while not self._uart.wait_tx_done(2):
                machine.idle()
            time.sleep_us(self._t35chars)
            self._ctrlPin(0)

        if self._debug:
            _logger.debug("UART {id} sent {ba}".format(id=self._id, ba=binascii.hexlify(serial_pdu).decode()))

    #@asynctimeit
    async def _send(self, modbus_pdu, slave_addr):
        serial_pdu = bytearray()
        serial_pdu.append(slave_addr)
        serial_pdu.extend(modbus_pdu)

        crc = self._calculate_crc16(serial_pdu)
        serial_pdu.extend(crc)

        await self._send_raw(serial_pdu)

    def trace_response(self, slave_addr, response):
        if self._debug:
            if response and len(response)>0:
                _logger.debug("UART {id} received '{ba}' from slave {slave_addr}".format(id=self._id, ba=binascii.hexlify(response).decode(), slave_addr=slave_addr))     
            else:
                 _logger.error("UART {id} response from slave {slave_addr} is empty".format(id=self._id, slave_addr=slave_addr)) 
    
    async def _send_receive(self, modbus_pdu, slave_addr, count: bool):
        # flush the Rx FIFO
        await self._uart_flush_rx_fifo()
        await self._send(modbus_pdu, slave_addr)
        response = await self._uart_read()
        self.trace_response(slave_addr, response)
        return self._validate_resp_hdr(response, slave_addr, modbus_pdu[0], count)        


    async def send_receive_raw(self, serial_pdu, count: bool):
        
        slave_addr = serial_pdu [0]
        function_code = serial_pdu [1]
        
        # flush the Rx FIFO
        await self._uart_flush_rx_fifo()
        await self._send_raw(serial_pdu)
        response = await self._uart_read(outbound_pdu=serial_pdu)
        self.trace_response(slave_addr, response)
        # Validate the header; if there are problems an exception will be raised
        if response and len(response)>0:
            validated_payload = self._validate_resp_hdr(response, slave_addr, function_code, count)
        else:
            _logger.error('UART {id}: Sent \'{out}\', {r}No data received from slave {slave_addr}{n}'.format(
                id=self._id, out=binascii.hexlify(serial_pdu), slave_addr=slave_addr,r=colors.BOLD_RED,n=colors.NORMAL))
            validated_payload = None
        # Return the full pdu received
        return response


    def _validate_resp_hdr(self, response, slave_addr, function_code, count: bool):

        if len(response) == 0:
            raise OSError('no data received from slave {slave_addr}'.format(slave_addr=slave_addr))

        resp_crc = response[-Const.CRC_LENGTH:]
        expected_crc = self._calculate_crc16(response[0:len(response) - Const.CRC_LENGTH])
        if (resp_crc[0] != expected_crc[0]) or (resp_crc[1] != expected_crc[1]):
            raise OSError('invalid response CRC from slave {slave_addr}'.format(slave_addr=slave_addr))

        if (response[0] != slave_addr):
            raise ValueError('wrong slave address, {a1} != {a2}'.format(a1=slave_addr, a2=response[0]))

        if (response[1] == (function_code + Const.ERROR_BIAS)):
            raise ValueError('slave {slave_addr} returned exception code: {c:d}'.format(slave_addr=slave_addr, c=response[2]))

        hdr_length = (Const.RESPONSE_HDR_LENGTH + 1) if count else Const.RESPONSE_HDR_LENGTH
        result = response[hdr_length : len(response) - Const.CRC_LENGTH]
        
        return result

    async def read_coils(self, slave_addr, starting_addr, coil_qty):
        modbus_pdu = functions.read_coils(starting_addr, coil_qty)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, True)
        status_pdu = self._bytes_to_bool(resp_data)

        return status_pdu

    async def read_discrete_inputs(self, slave_addr, starting_addr, input_qty):
        modbus_pdu = functions.read_discrete_inputs(starting_addr, input_qty)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, True)
        status_pdu = self._bytes_to_bool(resp_data)

        return status_pdu

    async def read_holding_registers(self, slave_addr, starting_addr, register_qty, signed=True):
        modbus_pdu = functions.read_holding_registers(starting_addr, register_qty)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, True)
        register_value = self._to_short(resp_data, signed)

        return register_value

    async def read_input_registers(self, slave_addr, starting_address, register_quantity, signed=True):
        modbus_pdu = functions.read_input_registers(starting_address, register_quantity)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, True)
        register_value = self._to_short(resp_data, signed)

        return register_value

    async def write_single_coil(self, slave_addr, output_address, output_value):
        modbus_pdu = functions.write_single_coil(output_address, output_value)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data, Const.WRITE_SINGLE_COIL,
                                                        output_address, value=output_value, signed=False)

        return operation_status

    async def write_single_register(self, slave_addr, register_address, register_value, signed=True):
        modbus_pdu = functions.write_single_register(register_address, register_value, signed)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data, Const.WRITE_SINGLE_REGISTER,
                                                        register_address, value=register_value, signed=signed)

        return operation_status

    async def write_multiple_coils(self, slave_addr, starting_address, output_values):
        modbus_pdu = functions.write_multiple_coils(starting_address, output_values)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data, Const.WRITE_MULTIPLE_COILS,
                                                        starting_address, quantity=len(output_values))

        return operation_status

    async def write_multiple_registers(self, slave_addr, starting_address, register_values, signed=True):
        modbus_pdu = functions.write_multiple_registers(starting_address, register_values, signed)

        resp_data = await self._send_receive(modbus_pdu, slave_addr, False)
        operation_status = functions.validate_resp_data(resp_data, Const.WRITE_MULTIPLE_REGISTERS,
                                                        starting_address, quantity=len(register_values))

        return operation_status

    async def send_response(self, slave_addr, function_code, request_register_addr, request_register_qty, request_data, values=None, signed=True):
        modbus_pdu = functions.response(function_code, request_register_addr, request_register_qty, request_data, values, signed)
        await self._send(modbus_pdu, slave_addr)

    async def send_exception_response(self, slave_addr, function_code, exception_code):
        modbus_pdu = functions.exception_response(function_code, exception_code)
        await self._send(modbus_pdu, slave_addr)

    async def get_request(self, unit_addr_list, timeout=None):
        req = await self._uart_read_frame(timeout)

        if len(req) < 8:
            return None

        if req[0] not in unit_addr_list:
            return None


        req_crc = req[-Const.CRC_LENGTH:]
        req_no_crc = req[:-Const.CRC_LENGTH]
        expected_crc = self._calculate_crc16(req_no_crc)
        if (req_crc[0] != expected_crc[0]) or (req_crc[1] != expected_crc[1]):
            return None

        try:
            request = Request(self, req_no_crc)
        except ModbusException as e:
            await self.send_exception_response(req[0], e.function_code, e.exception_code)
            return None

        return request
