# main.py
import time
import json
import  asyncio

from uModBus.async_serial import AsyncSerial
import planter_pinout as PINOUT

import logging
import gc

loop = asyncio.get_event_loop()
_logger = logging.getLogger("PlanterModbus")

baudrate=PINOUT.RS485_BAUDRATE
data_bits=PINOUT.RS485_DATABITS
stop_bits=PINOUT.RS485_STOPBIT
parity=PINOUT.RS485_PARITY
starting_address=0x0100
slave_addr=0x01

class PlanterModbus(object):


    @staticmethod
    async def modbus_scan_bus(modbus_obj):
        register_quantity=1
        signed=False

        # SCAN BUS:
        for slave_addr_i in range(253):
            try:
                register_value = await modbus_obj.read_holding_registers(slave_addr_i, starting_address, register_quantity, signed)
                if register_value is not None:
                    print('Slave ID '+ str(slave_addr_i) +' Holding register '+ starting_address +' value: ' + ' '.join('{:d}'.format(x) for x in register_value))
                else:
                    print('Slave ID '+ str(slave_addr_i) +' did not answer')
            except Exception as ex:
                _logger.exc(ex, 'Slave ID '+ str(slave_addr_i))                


    @staticmethod
    async def test_modbus():
        uart_id = PINOUT.RS485_UART

        print("Test modbus at (UART={id}, TX={tx}, RX={rx}, br={br}, {db} bits, {s} stop, partiy '{p}') - Slave Id {addr} register 0x{r:02X}".format(
            id=uart_id, tx=PINOUT.RS485_TXD, rx=PINOUT.RS485_RXD,
            br=baudrate, db=data_bits, s=stop_bits, p=parity,
            addr=slave_addr, r=starting_address
            ))

        modbus_obj = AsyncSerial(uart_id, tx_pin=PINOUT.RS485_TXD, rx_pin=PINOUT.RS485_RXD,
                                baudrate=baudrate, data_bits=data_bits,
                                stop_bits=stop_bits, parity=parity)

        # Soil moisture sensor: JXBS-3001-TR, mode RTU
        register_quantity=1
        signed=False

        for i in range(10):
            try:
                register_value = await modbus_obj.read_holding_registers(slave_addr, starting_address, register_quantity, signed)
                if register_value is not None:
                    print('Slave ID '+ str(slave_addr) +' Holding register value: ' + ' '.join('{:d}'.format(x) for x in register_value))
                else:
                    print('Slave ID '+ str(slave_addr) +' did not answer')
            except Exception as ex:
                _logger.exc(ex, 'Slave ID '+ str(slave_addr))
                


        del modbus_obj
        gc.collect()

    @staticmethod
    async def read(slave_id, br, addr, q):
        uart_id = PINOUT.RS485_UART

        print("Read modbus at (UART={id}, TX={tx}, RX={rx}, br={br}, {db} bits, {s} stop, partiy '{p}') - Slave Id {addr} register 0x{r:02X}".format(
            id=uart_id, tx=PINOUT.RS485_TXD, rx=PINOUT.RS485_RXD,
            br=br, db=data_bits, s=stop_bits, p=parity,
            addr=slave_id, r=addr
            ))

        modbus_obj = AsyncSerial(uart_id, tx_pin=PINOUT.RS485_TXD, rx_pin=PINOUT.RS485_RXD,
                                baudrate=br, data_bits=data_bits,
                                stop_bits=stop_bits, parity=parity)

        # Soil moisture sensor: JXBS-3001-TR, mode RTU
        register_quantity=1
        signed=False

        try:
            register_value = await modbus_obj.read_holding_registers(slave_id, addr, q, signed)
            if register_value is not None:
                print('Slave ID '+ str(slave_id) +' Holding register value: ' + ' '.join('{:d}'.format(x) for x in register_value))
            else:
                print('Slave ID '+ str(slave_id) +' did not answer')
        except Exception as ex:
            _logger.exc(ex, 'Slave ID '+ str(slave_id))
            

        del modbus_obj
        gc.collect()

    @staticmethod
    async def write(slave_id, br, addr, v):
        uart_id = PINOUT.RS485_UART

        print("Write modbus at (UART={id}, TX={tx}, RX={rx}, br={br}, {db} bits, {s} stop, partiy '{p}') - Slave Id {addr} register 0x{r:02X}".format(
            id=uart_id, tx=PINOUT.RS485_TXD, rx=PINOUT.RS485_RXD,
            br=br, db=data_bits, s=stop_bits, p=parity,
            addr=slave_id, r=addr
            ))

        modbus_obj = AsyncSerial(uart_id, tx_pin=PINOUT.RS485_TXD, rx_pin=PINOUT.RS485_RXD,
                                baudrate=br, data_bits=data_bits,
                                stop_bits=stop_bits, parity=parity)

        # Soil moisture sensor: JXBS-3001-TR, mode RTU
        register_quantity=1
        signed=False

        try:
            operation_status = await modbus_obj.write_single_register(slave_id, addr, v, signed)
            if operation_status is True:
                print('Slave ID '+ str(slave_id) +' write OK: ' + ' ')
            else:
                print('Slave ID '+ str(slave_id) +' write failed')
        except Exception as ex:
            _logger.exc(ex, 'Slave ID '+ str(slave_id))
            

        del modbus_obj
        gc.collect()

    @staticmethod
    async def cfg_speed():
        # Configure speed on RS-WS-N01-TR-1 to 9600 bps
        await PlanterModbus.write(1, 4800, 0x7d1,2)



def exec_test(name):

    if name == "main":
        coro = PlanterModbus.test_modbus()

    if name == "cfg_speed":
        coro = PlanterModbus.cfg_speed()

    loop.create_task(coro)
    print("Starting uasyncio loop with test {n}".format(n=name))
    try:
        loop.run_forever()
    except Exception as ex:
        _logger.exc(ex, "uasyncio loop exception")

def set_baudrate(value):
    global baudrate
    baudrate=value

def set_databits(value):
    global data_bits
    data_bits=value

def set_stopbits(value):
    global stop_bits
    stop_bits=value

def set_starting_address(value):
    global starting_address
    starting_address=value

def set_slave_addr(value):
    global slave_addr
    slave_addr=value

