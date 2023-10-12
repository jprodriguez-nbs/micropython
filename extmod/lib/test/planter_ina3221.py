# main.py
import time
import json
import esp32
import machine


import uasyncio as asyncio

import ina3221

import planter_pinout as PINOUT

_full_debug = False

class PlanterINA3221(object):

    def __init__(self):
        pass

    @staticmethod
    def ina3221_init(ina3221_dev):
        if ina3221.INA3221.IS_FULL_API:
            print("full API sample: improve accuracy")
            # improve accuracy by slower conversion and higher averaging
            # each conversion now takes 128*0.008 = 1.024 sec
            # which means 2 seconds per channel
            ina3221_dev.update(reg=ina3221.C_REG_CONFIG,
                        mask=ina3221.C_AVERAGING_MASK |
                        ina3221.C_VBUS_CONV_TIME_MASK |
                        ina3221.C_SHUNT_CONV_TIME_MASK |
                        ina3221.C_MODE_MASK,
                        value=ina3221.C_AVERAGING_256_SAMPLES |
                        ina3221.C_VBUS_CONV_TIME_332US |
                        ina3221.C_SHUNT_CONV_TIME_332US |
                        ina3221.C_MODE_SHUNT_AND_BUS_CONTINOUS)

        # enable all 3 channels. You can comment (#) a line to disable one
        name = ina3221_dev.name
        if _full_debug:
            s = ina3221_dev.current_config()
            print("{n} Start -> {s}".format(n=name, s=s))
        ina3221_dev.enable_channel(1)
        if _full_debug:
            s = ina3221_dev.current_config()
            print("{n} Enable CH1 -> {s}".format(n=name, s=s))
        ina3221_dev.enable_channel(2)
        if _full_debug:
            s = ina3221_dev.current_config()
            print("{n} Enable CH2 -> {s}".format(n=name, s=s))
        ina3221_dev.enable_channel(3)
        if _full_debug:
            s = ina3221_dev.current_config()
            print("{n} Enable CH3 -> {s}".format(n=name, s=s))


    @staticmethod
    def ina3221_cycle(ina3221_dev, bShow):

        if ina3221.INA3221.IS_FULL_API: # is_ready available only in "full" variant
            if not ina3221_dev.is_ready:
                #print ("INA3221 not ready, still measuring")
                return None

        if bShow:
            print("------------------------------")
            line_title =         "Measurement   "
            line_psu_voltage =   "PSU voltage   "
            line_load_voltage =  "Load voltage  "
            line_shunt_voltage = "Shunt voltage "
            line_current =       "Current       "

            #line_title_short =         "M   "
            #line_psu_voltage_short =   "V+  "
            #line_load_voltage_short =  "V-  "
            #line_shunt_voltage_short = "S mV"
            #line_current_short =       "I mA"

        l=[None, None, None, None, None]
        d=[None, None, None, None]
        l[0] = "{n:<3} V |   I [mA]".format(n=ina3221_dev.name)

        n=[None, "","",""]
        channel_names = ina3221_dev.channel_names
        if channel_names and len(channel_names)>=3:
            n[1] = channel_names[0]
            n[2] = channel_names[1]
            n[3] = channel_names[2]


        for chan in range(1,4):
            if ina3221_dev.is_channel_enabled(chan):
                bus_voltage = ina3221_dev.bus_voltage(chan)
                shunt_voltage = ina3221_dev.shunt_voltage(chan)
                current = ina3221_dev.current(chan)
            else:
                bus_voltage = 0
                shunt_voltage = 0
                current = 0



            if bShow:
                line_title +=         "| {c:d}- {n:<8} ".format(c=chan,n=n[chan])
                line_psu_voltage +=   "| {:6.3f}    V ".format(bus_voltage + shunt_voltage)
                line_load_voltage +=  "| {:6.3f}    V ".format(bus_voltage)
                line_shunt_voltage += "| {:9.6f} V ".format(shunt_voltage)
                line_current +=       "| {:9.6f} A ".format(current)

                #line_title_short +=         "| C{:d} ".format(chan)
                #line_psu_voltage_short +=   "|{:2.2f}".format(bus_voltage + shunt_voltage)
                #line_load_voltage_short +=  "|{:2.2f}".format(bus_voltage)
                #line_shunt_voltage_short += "|{:2.2f}".format(shunt_voltage*1000)
                #line_current_short +=       "|{:2.2f}".format(current*1000)

            v = bus_voltage + shunt_voltage
            p = v * current
            l[chan] = "{v:>6.3f}| {i:>8.3f}".format(v=bus_voltage + shunt_voltage, i=current*1000)
            d[chan]=(v, current, p)


        if bShow:
            print(line_title)
            print(line_psu_voltage)
            print(line_load_voltage)
            print(line_shunt_voltage)
            print(line_current)

        return (l,d)

    @staticmethod
    def ina3221_test(ina3221_dev):
        PlanterINA3221.ina3221_init(ina3221_dev)


        while True:
            if ina3221.INA3221.IS_FULL_API: # is_ready available only in "full" variant
                while not ina3221_dev.is_ready:
                    print(".",end='')
                    time.sleep(0.1)
                print("")
            PlanterINA3221.ina3221_cycle(ina3221_dev, True)
            time.sleep(2.0)
