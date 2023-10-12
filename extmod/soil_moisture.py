
import logging
from micropython import const
import machine

import sys
import os
import io
import utime

# Soil moisture sensor: JXBS-3001-TR, mode RTU
SLAVE_ADDR=const(0x01)

RS_SD_N01_TR_SOIL_HUMIDITY_REG = const(0x0000)
RS_SD_N01_TR_SOIL_TEMP_REG = const(0x0001)

JXBS_3001_SOIL_HUMIDITY_REG = const(0x0002)
JXBS_3001_SOIL_TEMPERATURE_REG = const(0x0003)
JXBS_3001_DEVICE_ADDRESS_REG = const(0x0100)
JXBS_3001_DEVICE_BAUDRATE_REG = const(0x0101)

MTEC_02A_SOIL_TEMPERATURE_REG = const(0x0000)
MTEC_02A_SOIL_VWC_REG = const(0x0001)
MTEC_02A_SOIL_EC_REG = const(0x0002)
MTEC_02A_SOIL_SALINITY_REG = const(0x0003)
MTEC_02A_SOIL_TDS_REG = const(0x0004)
MTEC_02A_SOIL_EPSILON_REG = const(0x0005)

MTEC_02A_SOIL_TYPE_REG = const(0x0020)
MTEC_02A_TEMP_UNIT_REG = const(0x0021)
MTEC_02A_EC_TEMP_COFF_REG = const(0x0022)
MTEC_02A_SALINITY_COFF_REG = const(0x0023)
MTEC_02A_TDS_COFF_REG = const(0x0024)

MTEC_02A_DEVICE_ADDRESS_REG = const(0x0200)
MTEC_02A_DEVICE_BAUDRATE_REG = const(0x0201)
MTEC_02A_DEVICE_PROTOCOL_REG = const(0x0202)
MTEC_02A_DEVICE_PARITY_REG = const(0x0203)
MTEC_02A_DEVICE_DATABITS_REG = const(0x0204)
MTEC_02A_DEVICE_STOPBITS_REG = const(0x0205)
MTEC_02A_DEVICE_RESPONSE_DELAY_10MS_REG = const(0x0206)
MTEC_02A_DEVICE_ACTIVE_OUTPUT_INTERVAL_S_REG = const(0x0207)


MODEL_JXBS_3001 = const(0)
MODEL_MTEC_02A = const(1)
MODEL_RS_ECTH_N01_B = const(2)
MODEL_RS_SD_N01_TR = const(3)

MODEL_JXBS_3001_STR = "jxbs-3001"
MODEL_MTEC_02A_STR = "mtec-02a"
MODEL_RS_ECTH_N01_B_STR = "rs-ecth-n01-b"
MODEL_RS_SD_N01_TR_STR = "rs-sd-n01-tr"

_model_dict = {
    MODEL_JXBS_3001_STR: MODEL_JXBS_3001,
    MODEL_MTEC_02A_STR: MODEL_MTEC_02A,
    MODEL_RS_ECTH_N01_B_STR: MODEL_RS_ECTH_N01_B,
    MODEL_RS_SD_N01_TR_STR : MODEL_RS_SD_N01_TR
}


class SoilMoistureData:

    def __init__(self, ts , name: str, vwc: float=None, temp: float=None, ec: float=None, salinity: float=None, tds: float=None, epsilon: float=None):
        self.ts = ts                # Timestamp of the data
        self.name = name            # Name of the sensor (because we may have more than one soil moisture sensor in the system)
        self.vwc = vwc              # Volume Water Content = Relative Humidity percentage [%]
        self.temp = temp            # Temperature in [celsius degrees]
        self.ec = ec                # Electro-Conductivity [us/cm]
        self.salinity = salinity    # Salinity [mg/L]
        self.tds = tds              # Total Dissolved Solids [mg/L]
        self.epsilon = epsilon      # Epsilon


class SoilMoistureSensor(object):

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value


    def setDebugLevel(self, level):
        self._logger.setLevel(level)

    def _report_vwc(self, new_vwc, msg):
        ts_now = utime.time()
        if self._last_reported_vwc is not None:
            d_abs = abs(self._last_reported_vwc- new_vwc)
        else:
            d_abs = new_vwc
        elapsed_s = ts_now - self._last_debug_output
        if d_abs > 0.2 or elapsed_s > 60:
            self._logger.info(msg)
            self._last_reported_vwc = new_vwc
            self._last_debug_output = ts_now


    def _report_exc(self, addr, ex, msg):
        ts_now = utime.time()
        if addr in self._last_reported_exc:
            elapsed_s = ts_now - self._last_reported_exc[addr]
        else:
            elapsed_s = 60
        if elapsed_s >= 60 or (msg != self._last_reported_exc_str):
            self._last_reported_exc[addr]=ts_now
            self._last_reported_exc_str = msg
            self._logger.exc(ex, msg)
        else:
            pass

    async def _read_jxbs_3001(self):
        try:
            start_addr = JXBS_3001_SOIL_HUMIDITY_REG
            register_value = await self._modbus.read_holding_registers(self._slave_addr, start_addr, 1, True)
            if register_value is not None:
                self._smd.ts = self._rtc.datetime()
                #self._smd.temp = register_value[JXBS_3001_SOIL_TEMPERATURE_REG]/10.0

                new_vwc = register_value[JXBS_3001_SOIL_HUMIDITY_REG-start_addr]/10.0
                if self._smd.vwc is not None:
                    d_abs = abs(self._smd.vwc - new_vwc)
                else:
                    d_abs = new_vwc

                if (d_abs > 1)  or (self._smd.vwc is None):
                    self._smd.vwc = new_vwc
                else:
                    if self._smd.vwc is not None:
                        self._smd.vwc = self._smd.vwc * 0.9 + new_vwc * 0.1
                    else:
                        self._smd.vwc = new_vwc

                #reg_str = ", ".join(["0x{r:04X}".format(r=r) for r in register_value])
                self._report_vwc(self._smd.vwc, "HR {hr:>5.2f}%".format(hr=self._smd.vwc))

                if (self._smd.vwc is not None) and ((self._smd.vwc != 0) or (self._successful_reads_counter>3)):
                    self._read_succeeded = True
                    
                self._successful_reads_counter += 1
            else:
                self._logger.warning('Slave {n} - ID {a} did not answer'.format(n=self._name, a=self._slave_addr))
                self._smd.vwc = None
                #self._smd.temp = None
                self._read_succeeded = False
        except Exception as ex:
            self._report_exc(self._slave_addr, ex, 'Slave {n} - ID {a} error: {e}'.format(n=self._name, a=self._slave_addr, e=str(ex)))

        return [self._smd, self._read_succeeded]

    async def _read_rs_sd_n01_tr(self):
        try:
            start_addr = RS_SD_N01_TR_SOIL_HUMIDITY_REG
            register_value = await self._modbus.read_holding_registers(self._slave_addr, start_addr, 2, True)
            if register_value is not None:
                self._smd.ts = self._rtc.datetime()
                #self._smd.temp = register_value[JXBS_3001_SOIL_TEMPERATURE_REG]/10.0

                new_vwc = register_value[RS_SD_N01_TR_SOIL_HUMIDITY_REG-start_addr]/10.0
                if self._smd.vwc is not None:
                    d_abs = abs(self._smd.vwc - new_vwc)
                else:
                    d_abs = new_vwc

                if (d_abs > 1)  or (self._smd.vwc is None):
                    self._smd.vwc = new_vwc
                else:
                    if self._smd.vwc is not None:
                        self._smd.vwc = self._smd.vwc * 0.9 + new_vwc * 0.1
                    else:
                        self._smd.vwc = new_vwc

                self._smd.temp = register_value[RS_SD_N01_TR_SOIL_TEMP_REG-start_addr]/10.0

                #reg_str = ", ".join(["0x{r:04X}".format(r=r) for r in register_value])
                self._report_vwc(self._smd.vwc, "HR {hr:>5.2f}%".format(hr=self._smd.vwc))

                if (self._smd.vwc is not None) and ((self._smd.vwc != 0) or (self._successful_reads_counter>3)):
                    self._read_succeeded = True
                    
                self._successful_reads_counter += 1
            else:
                self._logger.warning('Slave {n} - ID {a} did not answer'.format(n=self._name, a=self._slave_addr))
                self._smd.vwc = None
                #self._smd.temp = None
                self._read_succeeded = False
        except Exception as ex:
            self._report_exc(self._slave_addr, ex, 'Slave {n} - ID {a} error: {e}'.format(n=self._name, a=self._slave_addr, e=str(ex)))

        return [self._smd, self._read_succeeded]

    async def _read_mtec_02a(self):
        try:
            register_value = await self._modbus.read_holding_registers(self._slave_addr, 0, 6, True)
            if register_value is not None:
                self._smd.ts = self._rtc.datetime()
                self._smd.temp = register_value[0]/100.0
                self._smd.ec = register_value[2]
                self._smd.salinity = register_value[3]
                self._smd.tds = register_value[4]
                self._smd.epsilon = register_value[5]/100.0

                new_vwc = register_value[1]/100.0

                if self._smd.vwc is not None:
                    d_abs = abs(self._smd.vwc - new_vwc)
                else:
                    d_abs = new_vwc
                if (d_abs > 1)  or (self._smd.vwc is None):
                    self._smd.vwc = new_vwc
                else:
                    if self._smd.vwc is not None:
                        self._smd.vwc = self._smd.vwc * 0.9 + new_vwc * 0.1
                    else:
                        self._smd.vwc = new_vwc

                self._report_vwc(self._smd.vwc, "HR {hr:>5.2f}%, T {t:>5.2f} oC, ec {ec} [us/cm], salinity {sal} [mg/L], tds {tds} [mg/L], epsilon {e}".format(
                        hr=self._smd.vwc, t=self._smd.temp, ec=self._smd.ec, sal=self._smd.salinity, tds=self._smd.tds, e=self._smd.epsilon))

                if (self._smd.vwc is not None) and (self._smd.temp is not None) and ((self._smd.vwc != 0) or (self._smd.temp != 0) or (self._successful_reads_counter>3)):
                    self._read_succeeded = True

                self._successful_reads_counter += 1
            else:
                self._logger.warning('Slave {n} - ID {a} did not answer'.format(n=self._name, a=self._slave_addr))
                self._smd.vwc = None
                self._smd.temp = None
                self._smd.ec = None
                self._smd.salinity = None
                self._smd.tds = None
                self._smd.epsilon = None
                self._read_succeeded = False
        except Exception as ex:
            self._report_exc(self._slave_addr, ex, 'Slave {n} - ID {a} error: {e}'.format(n=self._name, a=self._slave_addr, e=str(ex)))

        return [self._smd, self._read_succeeded]

    async def _read_rs_ecth_n01_b(self):
        try:
            register_value = await self._modbus.read_holding_registers(self._slave_addr, 0, 6, True)
            if register_value is not None:
                
                self._smd.ts = self._rtc.datetime()
                self._smd.temp = register_value[1]/100.0
                self._smd.ec = register_value[2]
                self._smd.salinity = register_value[3]
                self._smd.tds = register_value[4]
                self._smd.epsilon = register_value[5]/100.0

                new_vwc = register_value[0]/100.0

                if self._smd.vwc is not None:
                    d_abs = abs(self._smd.vwc - new_vwc)
                else:
                    d_abs = new_vwc
                if d_abs>1:
                    self._smd.vwc = new_vwc
                else:
                    if self._smd.vwc is not None:
                        self._smd.vwc = self._smd.vwc * 0.9 + new_vwc * 0.1
                    else:
                        self._smd.vwc = new_vwc

                self._report_vwc(self._smd.vwc, "HR {hr:>5.2f}%, T {t:>5.2f} oC, ec {ec} [us/cm], salinity {sal} [mg/L], tds {tds} [mg/L], epsilon {e}".format(
                        hr=self._smd.vwc, t=self._smd.temp, ec=self._smd.ec, sal=self._smd.salinity, tds=self._smd.tds, e=self._smd.epsilon))

                if (self._smd.vwc is not None) and (self._smd.temp is not None) and ((self._smd.vwc != 0) or (self._smd.temp != 0) or (self._successful_reads_counter>3)):
                    self._read_succeeded = True

                self._successful_reads_counter += 1
            else:
                self._logger.warning('Slave ID {a} did not answer'.format(a=self._slave_addr))
                self._smd.vwc = None
                self._smd.temp = None
                self._smd.ec = None
                self._smd.salinity = None
                self._smd.tds = None
                self._smd.epsilon = None
                self._read_succeeded = False
        except Exception as ex:
            self._report_exc(self._slave_addr, ex, 'Slave {n} - ID {a} error: {e}'.format(n=self._name, a=self._slave_addr, e=str(ex)))

        return [self._smd, self._read_succeeded]

    async def read(self):
        result = None
        try:
            if self._model == MODEL_JXBS_3001:
                result =  await self._read_jxbs_3001()
            elif self._model == MODEL_RS_SD_N01_TR:
                result =  await self._read_rs_sd_n01_tr()
            elif self._model == MODEL_MTEC_02A:
                result =  await self._read_mtec_02a()
            elif self._model == MODEL_RS_ECTH_N01_B:
                result =  await self._read_rs_ecth_n01_b()
            else:
                self._logger.error("SM sensor {n}, model {m}, address {a} UNKNOWN".format(n=self._fullname, m=self._model, a=self._slave_addr))
                return None
        except Exception as ex:
            #_handle_exception(self._logger, 'Slave ID {a} exception: {e}'.format(a=self._slave_addr, e=str(ex)), E)
            self._logger.exc(ex, 'Slave ID {a} exception: {e}'.format(a=self._slave_addr, e=str(ex)))
        
        
        return result

    async def test(self, a=None):
        result = False
        if a is None:
            a=self._slave_addr
        try:
            if self._model == MODEL_JXBS_3001:
                register_value = await self._modbus.read_holding_registers(a, JXBS_3001_DEVICE_ADDRESS_REG, 1, False)
                m = MODEL_JXBS_3001_STR
            elif self._model == MODEL_RS_SD_N01_TR:
                register_value = await self._modbus.read_holding_registers(a, MTEC_02A_DEVICE_ADDRESS_REG, 1, False)
                m = MODEL_RS_SD_N01_TR_STR
            elif self._model == MODEL_MTEC_02A or self._model == MODEL_RS_ECTH_N01_B:
                register_value = await self._modbus.read_holding_registers(a, MTEC_02A_DEVICE_ADDRESS_REG, 1, False)
                m = MODEL_MTEC_02A_STR
            else:
                return None
            if register_value is not None and register_value[0] == a:
                result = True
                self._logger.debug("Found soil moisture sensor {name} model {m} at address {a}".format(name=self._name, m=m, a=a))
            else:
                self._logger.warning('Slave ID {a} did not answer'.format(a=a))
        except Exception as ex:
            self._report_exc(self._slave_addr, ex, 'Slave {n} - ID {a} error: {e}'.format(n=self._name, a=self._slave_addr, e=str(ex)))

        return result

    async def search(self, cb=None):
        r = False

        r = await self.test(self._slave_addr)
        if r is False:
            for a in range(1,255):
                r = await self.test(a)
                if r:
                    break
                if cb is not None:
                    cb()
        return r


    async def scan(self, full=False):
        r = False

        for slave_id in range(1,255):
            self._logger.debug("Scan RS-485 slave {slave_id}".format(slave_id=slave_id))
            for a in range(6):
                try:
                    register_value = await self._modbus.read_holding_registers(slave_id, a, 1, False)
                except:
                    register_value = None
                if register_value is not None:
                    self._logger.debug("Found RS-485 slave {slave_id}, answer register {a} -> {v}".format(slave_id=slave_id, a=a, v=register_value[0]))
                    r = True
                    if full is False: break
        return r


    def __init__(self, modbus, name="", model = MODEL_JXBS_3001, slave_addr = SLAVE_ADDR):        
        self._name = name
        self._fullname = "SoilMoisture[{n}]".format(n=name)
        self._logger = logging.getLogger(self._fullname)
        self._logger.setLevel(logging.DEBUG)

        self._slave_addr = slave_addr
        self._modbus = modbus
        self._read_succeeded = False
        self._rtc = machine.RTC()
        self._smd = SoilMoistureData (
                    ts = self._rtc.datetime(),
                    name = self._name
                )
        #self._last_debug_output = utime.time()
        self._last_debug_output = 0
        self._last_reported_vwc = None
        self._last_reported_exc = {}
        self._last_reported_exc_str = ""

        # Count number of successful reads. After 5 reads we will accept the values even if they are zero
        # which is the case when the sensor is not in the ground
        self._successful_reads_counter = 0

        try:
            if isinstance(model, str):
                if model in _model_dict:
                    model = _model_dict[model]
                else:
                    self._logger.error('Model {m} is unknown'.format(m=model))
                    model = MODEL_RS_ECTH_N01_B
            self._model = model
        except Exception as ex:
            self._logger.exc(ex, 'Failed to set model {m}'.format(m=model))
            self._model = MODEL_RS_ECTH_N01_B