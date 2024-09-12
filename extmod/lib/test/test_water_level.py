import time
import os
import io
import sys

import logging

import json
import esp32
import machine
import gc
import uasyncio as asyncio
from machine import Pin, sleep, time_pulse_us, disable_irq, enable_irq, Timer, WDT
import mcp23017
import hwversion
import utime
import planter_pinout as PINOUT



async def monitor_mcp(mcp, mode):
    a = mcp.porta.gpio
    b = mcp.portb.gpio

    # Remove flow data to avoid frequent updates when pumping water
    result = (
                0,
                (a&PINOUT.DI_A_RAIN_BIT) == PINOUT.DI_A_RAIN_BIT,
                (a&PINOUT.DI_A_DOOR_BIT) == PINOUT.DI_A_DOOR_BIT,
                ((a&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE,
                (a&PINOUT.DI_A_ACC_INT1_BIT) == PINOUT.DI_A_ACC_INT1_BIT,
                (a&PINOUT.DI_A_ACC_INT2_BIT) == PINOUT.DI_A_ACC_INT2_BIT,
                (a&PINOUT.DI_A_BUTTON_1) == PINOUT.DI_A_BUTTON_1,
                (a&PINOUT.DI_A_NSMBALERT) == PINOUT.DI_A_NSMBALERT,
                (a&PINOUT.DI_A_SOCALERT) == PINOUT.DI_A_SOCALERT,
            a,
            b
            )
    door_open = result[PINOUT.DOOR_IDX]
    level_low = result[PINOUT.LEVEL_IDX]

    f_str = "Level Mode = {m}, A = {a:08b}  B = {b:08b}, door_open={door_open}, level_low={level_low}".format(
            m=mode, a=a, b=b, door_open=door_open, level_low=level_low)
    print (f_str)

async def detect_water_level_sensor(mcp):
    # Backup original value
    b_orig = mcp.portb.gpio

    b_detected = False

    for i in range(20):
        # Switch mode line
        mcp.portb.gpio = 0x0E | PINOUT.DO_B_LEVEL_MODE
        await asyncio.sleep_ms(50)
        a_mode_1 = mcp.porta.gpio
        l_mode_1 = ((a_mode_1&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE

        #await monitor_mcp(mcp, True)

        mcp.portb.gpio = 0x0E & ((~PINOUT.DO_B_LEVEL_MODE) &0xFF)
        await asyncio.sleep_ms(50)
        a_mode_0 = mcp.porta.gpio
        l_mode_0 = ((a_mode_0&PINOUT.DI_A_LEVEL_LOW_BIT) == PINOUT.DI_A_LEVEL_LOW_BIT) is PINOUT.LEVEL_LOW_ACTIVE

        #await monitor_mcp(mcp, False)
    
        if l_mode_0 != l_mode_1:
            b_detected = True
            break
        
    # Compare
    if b_detected:
        print ("WaterLevel sensor detected.")
    else:
        print ("Failed to detect WaterLevel sensor.")
    
    # Restore original value
    mcp.portb.gpio = b_orig

    return b_detected

#
async def test_water_level(mcp, mode=True, time=15):

    for i in range(20):
        await detect_water_level_sensor(mcp)
        

    v = 0x0E
    if mode:
        v = v | PINOUT.DO_B_LEVEL_MODE
    mcp.portb.gpio = v

    for i in range(time*2):
        await monitor_mcp(mcp, mode)
        await asyncio.sleep_ms(500)

    
