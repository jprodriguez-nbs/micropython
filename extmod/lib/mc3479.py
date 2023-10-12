from micropython import const
import machine
from machine import Pin, SPI

import planter_pinout as PINOUT

import logging

import utime
import struct
import ubinascii

#*****************************************************************************
#*** CONSTANT / DEFINE
#*****************************************************************************
MC34X9_RETCODE_SUCCESS                = (0)
MC34X9_RETCODE_ERROR_BUS              = (-1)
MC34X9_RETCODE_ERROR_NULL_POINTER     = (-2)
MC34X9_RETCODE_ERROR_STATUS           = (-3)
MC34X9_RETCODE_ERROR_SETUP            = (-4)
MC34X9_RETCODE_ERROR_GET_DATA         = (-5)
MC34X9_RETCODE_ERROR_IDENTIFICATION   = (-6)
MC34X9_RETCODE_ERROR_NO_DATA          = (-7)
MC34X9_RETCODE_ERROR_WRONG_ARGUMENT   = (-8)
MC34X9_FIFO_DEPTH                     =   32
MC34X9_REG_MAP_SIZE                   =   64

#******************************************************************************
#*** CONSTANT / DEFINE
#*****************************************************************************
MC34X9_INTR_C_IPP_MODE_OPEN_DRAIN  =  (0x00)
MC34X9_INTR_C_IPP_MODE_PUSH_PULL   =  (0x01)

MC34X9_INTR_C_IAH_ACTIVE_LOW       =  (0x00)
MC34X9_INTR_C_IAH_ACTIVE_HIGH      =  (0x01)

MC34X9_AUTO_CLR_DISABLE            =  (0x00)
MC34X9_AUTO_CLR_ENABLE             =  (0x01)

#******************************************************************************
#*** Register Map
#*****************************************************************************
MC34X9_REG_DEV_STAT        = (0x05)
MC34X9_REG_INTR_CTRL       = (0x06)
MC34X9_REG_MODE            = (0x07)
MC34X9_REG_SR              = (0x08)
MC34X9_REG_MOTION_CTRL     = (0x09)
MC34X9_REG_FIFO_STAT       = (0x0A)
MC34X9_REG_FIFO_RD_P       = (0x0B)
MC34X9_REG_FIFO_WR_P       = (0x0C)
MC34X9_REG_XOUT_LSB        = (0x0D)
MC34X9_REG_XOUT_MSB        = (0x0E)
MC34X9_REG_YOUT_LSB        = (0x0F)
MC34X9_REG_YOUT_MSB        = (0x10)
MC34X9_REG_ZOUT_LSB        = (0x11)
MC34X9_REG_ZOUT_MSB        = (0x12)
MC34X9_REG_STATUS          = (0x13)
MC34X9_REG_INTR_STAT       = (0x14)
MC34X9_REG_PROD            = (0x18)
MC34X9_REG_RANGE_C         = (0x20)
MC34X9_REG_XOFFL           = (0x21)
MC34X9_REG_XOFFH           = (0x22)
MC34X9_REG_YOFFL           = (0x23)
MC34X9_REG_YOFFH           = (0x24)
MC34X9_REG_ZOFFL           = (0x25)
MC34X9_REG_ZOFFH           = (0x26)
MC34X9_REG_XGAIN           = (0x27)
MC34X9_REG_YGAIN           = (0x28)
MC34X9_REG_ZGAIN           = (0x29)
MC34X9_REG_FIFO_CTRL       = (0x2D)
MC34X9_REG_FIFO_TH         = (0x2E)
MC34X9_REG_FIFO_INTR       = (0x2F)
MC34X9_REG_FIFO_CTRL_SR2   = (0x30)
MC34X9_REG_COMM_CTRL       = (0x31)
MC34X9_REG_GPIO_CTRL       = (0x33)
MC34X9_REG_TF_THRESH_LSB   = (0x40)
MC34X9_REG_TF_THRESH_MSB   = (0x41)
MC34X9_REG_TF_DB           = (0x42)
MC34X9_REG_AM_THRESH_LSB   = (0x43)
MC34X9_REG_AM_THRESH_MSB   = (0x44)
MC34X9_REG_AM_DB           = (0x45)
MC34X9_REG_SHK_THRESH_LSB  = (0x46)
MC34X9_REG_SHK_THRESH_MSB  = (0x47)
MC34X9_REG_PK_P2P_DUR_THRESH_LSB   = (0x48)
MC34X9_REG_PK_P2P_DUR_THRESH_MSB   = (0x49)
MC34X9_REG_TIMER_CTRL      = (0x4A)

MC34X9_NULL_ADDR           = (0)

MC34X9_CHIP_ID = (0xA4)

s_bCfgFTThr = 200
s_bCfgFTDebounce = 50

class MC34X9_acc_t():
    def __init__(self):
        self.XAxis = 0
        self.YAxis = 0
        self.ZAxis = 0
        self.XAxis_g = 0.0
        self.YAxis_g = 0.0
        self.ZAxis_g = 0.0

class MC34X9_gain_t():
    MC34X9_GAIN_5_24X      = 0b0011
    MC34X9_GAIN_3_89X      = 0b0010
    MC34X9_GAIN_DEFAULT_1X = 0b0000
    MC34X9_GAIN_0_5X       = 0b0100
    MC34X9_GAIN_0_33X      = 0b1100


class MC34X9_mode_t():
    MC34X9_MODE_SLEEP    = 0b000
    MC34X9_MODE_CWAKE      = 0b001
    MC34X9_MODE_RESERVED   = 0b010
    MC34X9_MODE_STANDBY  = 0b011


class MC34X9_range_t():
    MC34X9_RANGE_2G    = 0b000
    MC34X9_RANGE_4G    = 0b001
    MC34X9_RANGE_8G    = 0b010
    MC34X9_RANGE_16G   = 0b011
    MC34X9_RANGE_12G   = 0b100
    MC34X9_RANGE_END   = MC34X9_RANGE_12G+1

class MC34X9_sr_t():
    MC34X9_SR_25Hz            = 0x10
    MC34X9_SR_50Hz            = 0x11
    MC34X9_SR_62_5Hz          = 0x12
    MC34X9_SR_100Hz           = 0x13
    MC34X9_SR_125Hz           = 0x14
    MC34X9_SR_250Hz           = 0x15
    MC34X9_SR_500Hz           = 0x16
    MC34X9_SR_DEFAULT_1000Hz  = 0x17
    MC34X9_SR_END = MC34X9_SR_DEFAULT_1000Hz+1


class MC34X9_motion_feature_t():
    MC34X9_TILT_FEAT = 0
    MC34X9_ANYM_FEAT = 2
    MC34X9_SHAKE_FEAT = 3
    MC34X9_TILT35_FEAT = 4


class MC34X9_fifo_ctl_t():
    MC34X9_FIFO_CTL_DISABLE = 0
    MC34X9_FIFO_CTL_ENABLE = 1
    MC34X9_FIFO_CTL_END = 2


class MC34X9_fifo_mode_t():
    MC34X9_FIFO_MODE_NORMAL = 0
    MC34X9_FIFO_MODE_WATERMARK = 1
    MC34X9_FIFO_MODE_END = 2


class MC34X9_fifo_int_t():
    MC34X9_COMB_INT_DISABLE = 0
    MC34X9_COMB_INT_ENABLE = 1
    MC34X9_COMB_INT_END = 2


class MC34X9_interrupt_event_t():
    def __init__(self):
        self.r=0
        self.bTILT=0
        self.bFLIP=0
        self.bANYM=0
        self.bSHAKE=0
        self.bTILT_35=0
        self.bRESV=0
        self.bAUTO_CLR=0
        self.bACQ=0
    def has_interrupt(self):
        r = self.bTILT or self.bFLIP or self.bANYM or self.bSHAKE or self.bTILT_35 or self.bRESV or self.bAUTO_CLR or self.bACQ
        return r


class MC34X9_fifo_interrupt_event_t():
    def __init__(self):
        self.r = 0
        self.bFIFO_EMPTY=0
        self.bFIFO_FULL=0
        self.bFIFO_THRESH=0
    def has_interrupt(self):
        r = self.bFIFO_EMPTY or self.bFIFO_FULL or self.bFIFO_THRESH
        return r

# ***I2C/SPI BUS***
        
class e_m_drv_interface_spimode_t():
  #/** SPI run under 2MHz when normal mode enable. */
  E_M_DRV_INTERFACE_SPIMODE_NORMAL = 0
  #/** SPI bus could over 2MHz after enable high speed mode. */
  E_M_DRV_INTERFACE_SPIMODE_HS = 1
  E_M_DRV_INTERFACE_SPIMODE_END = 2


# ***MC34X9 driver motion part***
class MC34X9_TILT35_DURATION_TIMER_t:
    MC34X9_TILT35_1p6           = 0b000
    MC34X9_TILT35_1p8           = 0b001
    MC34X9_TILT35_2p0           = 0b010  
    MC34X9_TILT35_2p2           = 0b011
    MC34X9_TILT35_2p4           = 0b100
    MC34X9_TILT35_2p6           = 0b101
    MC34X9_TILT35_2p8           = 0b110
    MC34X9_TILT35_3p0           = 0b111


#*****************************************************************************
#*** Motion threshold and debounce config
#*****************************************************************************
s_bCfgFTThr              = 100
s_bCfgFTDebounce         = 50

s_bCfgANYMThr            = 200 #200
s_bCfgANYMDebounce       = 100 #100

s_bCfgShakeThr           = 300
s_bCfgShakeP2PDuration   = 10
s_bCfgShakeCount         = 1

s_bCfgTILT35Thr          = 20
s_bCfgTILT35Timer        = MC34X9_TILT35_DURATION_TIMER_t.MC34X9_TILT35_2p0

MC34X9_CFG_MODE_DEFAULT                = MC34X9_mode_t.MC34X9_MODE_STANDBY
MC34X9_CFG_SAMPLE_RATE_DEFAULT         = MC34X9_sr_t.MC34X9_SR_DEFAULT_1000Hz
MC34X9_CFG_RANGE_DEFAULT               = MC34X9_range_t.MC34X9_RANGE_16G


#// *** FIFO control ***/
FIFO_THRE_SIZE = 30
#// FIFO Interrupt
enableFifoThrINT = False
#// For FIFO feature, enable FIFO interrupt will automatically enable FIFO feature
enableFIFO = False

#// Enabling motion feature below also enables corresponded motion interrupt
enableTILT = False
enableFLIP = False
enableANYM = True
enableSHAKE = False
enableTILT35 = False

#// Determine if enable interrupt
interruptEnabled = enableFifoThrINT or enableTILT or enableFLIP or enableANYM or enableSHAKE or enableTILT35

# general accel methods
class MC34X9():

    def __init__(self, bSpi, chip_select, drv, i2c_address):
        self.CfgRange = 0
        self.CfgFifo = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.AccRaw = MC34X9_acc_t()
        self.pin_cs = None
        self.logger = logging.getLogger("MC34X9")
        self.logger.setLevel(logging.ERROR)
        self._sensor_impact_th = None

        self._buffer_out_1 = bytearray(1)
        self._buffer_out_2 = bytearray(2)
        self._buffer = bytearray(6)

        #/** 0 = SPI, 1 = I2C */
        self.M_bSpi = bSpi
        self.M_chip_select = chip_select
        self.i2c_addr = i2c_address
        if not bSpi:
            self.logger.debug("SPI mode")
            #// Chip select pin
            self.pin_cs = machine.Pin(chip_select, machine.Pin.OUT, value=True)
            #// Initialize SPI
            #self.spi = SPI(PINOUT.SPI_HOST, baudrate=4000000, polarity=1, phase=0, sck=Pin(PINOUT.SPI_CLK), mosi=Pin(PINOUT.SPI_MOSI), miso=Pin(PINOUT.SPI_MISO))
            self.spi = drv
        else:
            self.logger.debug("I2C mode")
            #// Initialize I2C
            self.i2c = drv

        #Initialize the MC34X9 sensor and set as the default configuration
        #//Init Reset
        self.reset()
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)

        #/* Check I2C connection */
        id = self.readRegister8(MC34X9_REG_PROD)
        if id != MC34X9_CHIP_ID:
            #/* No MC34X9 detected ... return False */
            self.logger.debug("No MC34X9 detected!")
            self.logger.debug("Chip ID: 0x{a:02X}".format(a=id))
            self.available = False
            return
        
        #Range: 8g
        self.SetRangeCtrl(MC34X9_CFG_RANGE_DEFAULT)
        #Sampling Rate: 50Hz by default
        self.SetSampleRate(MC34X9_CFG_SAMPLE_RATE_DEFAULT)
        #Mode: Active
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_CWAKE)

        # Check
        self.GetRangeCtrl()
        self.GetSampleRate()

        utime.sleep_ms(50)

        self.available = True


    @property
    def name(self):
        return "MC3479"

    # Set debug level
    def setLevel(self, l):
        self.logger.setLevel(l)

    def wake(self):
        #//Set mode as wake
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_CWAKE)
        

    def stop(self):
        #//Set mode as Sleep
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)


    #//Initial reset
    def reset(self):
        #// Stand by mode
        self.writeRegister8(MC34X9_REG_MODE, MC34X9_mode_t.MC34X9_MODE_STANDBY)

        utime.sleep_ms(10)

        #// power-on-reset
        self.writeRegister8(0x1c, 0x40)

        utime.sleep_ms(50)

        #// Disable interrupt
        self.writeRegister8(0x06, 0x00)
        utime.sleep_ms(10)
        #// 1.00x Aanalog Gain
        self.writeRegister8(0x2B, 0x00)
        utime.sleep_ms(10)
        #// DCM disable
        self.writeRegister8(0x15, 0x00)

        utime.sleep_ms(50)


    #//Set the operation mode: MC34X9_mode_t
    def SetMode(self, mode):
        value = 0

        value = self.readRegister8(MC34X9_REG_MODE)
        value &= 0b11110000
        value |= mode

        self.writeRegister8( MC34X9_REG_MODE, value)


    #//Set the range control MC34X9_range_t
    def SetRangeCtrl(self, range ):
        value = 0
        self.CfgRange = range
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)
        value = self.readRegister8(MC34X9_REG_RANGE_C)
        value &= 0b00000111
        value |= (range << 4) & 0x70
        self.writeRegister8(MC34X9_REG_RANGE_C, value)


    #//Set the sampling rate MC34X9_sr_t
    def SetSampleRate(self, sample_rate):
        value = 0
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)
        value = self.readRegister8(MC34X9_REG_SR)
        value &= 0b00000000
        value |= sample_rate
        self.writeRegister8(MC34X9_REG_SR, value)
        

    #// Set Motion feature
    # int tilt_ctrl,  int flip_ctl, int anym_ctl, int shake_ctl, int tilt_35_ctl
    def SetMotionCtrl(self, tilt_ctrl, flip_ctl, anym_ctl, shake_ctl, tilt_35_ctl):
        CfgMotion = 0

        if (tilt_ctrl or flip_ctl):
            self._M_DRV_MC34X6_SetTilt_Flip()
            CfgMotion |= (((tilt_ctrl | flip_ctl) & 0x01) << MC34X9_motion_feature_t.MC34X9_TILT_FEAT)
        

        if (anym_ctl):
            self._M_DRV_MC34X6_SetAnym()
            CfgMotion |= ((anym_ctl & 0x01) << MC34X9_motion_feature_t.MC34X9_ANYM_FEAT)
        

        if (shake_ctl):
            self._M_DRV_MC34X6_SetShake()
            #// Also enable anyMotion feature
            CfgMotion |= ((shake_ctl & 0x01) << MC34X9_motion_feature_t.MC34X9_ANYM_FEAT) | ((shake_ctl & 0x01) << MC34X9_motion_feature_t.MC34X9_SHAKE_FEAT)
        

        if (tilt_35_ctl):
            self._M_DRV_MC34X6_SetTilt35()
            #// Also enable anyMotion feature
            CfgMotion |= ((tilt_35_ctl & 0x01) << MC34X9_motion_feature_t.MC34X9_ANYM_FEAT) | ((tilt_35_ctl & 0x01) << MC34X9_motion_feature_t.MC34X9_TILT35_FEAT)
        

        self.writeRegister8(MC34X9_REG_MOTION_CTRL, CfgMotion)


    #//Set FIFO feature fifo_ctl: MC34X9_fifo_ctl_t, fifo_mode: MC34X9_fifo_mode_t, fifo_thr: int
    def SetFIFOCtrl(self, fifo_ctl: int, fifo_mode: int, fifo_thr: int):
        if (fifo_thr > 31):  #//maximum threshold
            fifo_thr = 31

        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)

        self.CfgFifo = (MC34X9_fifo_int_t.MC34X9_COMB_INT_ENABLE << 3) | ((fifo_ctl << 5) | (fifo_mode << 6))

        self.writeRegister8(MC34X9_REG_FIFO_CTRL, self.CfgFifo)

        CfgFifoThr = fifo_thr & 0xFF
        self.writeRegister8(MC34X9_REG_FIFO_TH, CfgFifoThr)


    def SetGerneralINTCtrl(self):
        #// Gerneral Interrupt setup

        CfgGPIOINT = (((MC34X9_INTR_C_IAH_ACTIVE_HIGH & 0x01) << 2) #// int1
                            | ((MC34X9_INTR_C_IPP_MODE_OPEN_DRAIN & 0x01) << 3)#// int1
                            | ((MC34X9_INTR_C_IAH_ACTIVE_HIGH & 0x01) << 6)#// int2
                            | ((MC34X9_INTR_C_IPP_MODE_OPEN_DRAIN & 0x01) << 7));#// int2

        self.writeRegister8(MC34X9_REG_GPIO_CTRL, CfgGPIOINT)


    #//Set interrupt control register
    def SetINTCtrl(self, tilt_int_ctrl, flip_int_ctl, anym_int_ctl, shake_int_ctl, tilt_35_int_ctl):
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)

        CfgINT = (((tilt_int_ctrl & 0x01) << 0)
                            | ((flip_int_ctl & 0x01) << 1)
                            | ((anym_int_ctl & 0x01) << 2)
                            | ((shake_int_ctl & 0x01) << 3)
                            | ((tilt_35_int_ctl & 0x01) << 4)
                            | ((MC34X9_AUTO_CLR_ENABLE & 0x01) << 6))
        self.writeRegister8(MC34X9_REG_INTR_CTRL, CfgINT)

        self.SetGerneralINTCtrl()


    #//Set FIFO interrupt control register
    def SetFIFOINTCtrl(self, fifo_empty_int_ctl, fifo_full_int_ctl, fifo_thr_int_ctl):
        self.SetMode(MC34X9_mode_t.MC34X9_MODE_STANDBY)

        self.CfgFifo = self.CfgFifo \
                    | (((fifo_empty_int_ctl & 0x01) << 0)
                    | ((fifo_full_int_ctl & 0x01) << 1)
                    | ((fifo_thr_int_ctl & 0x01) << 2))

        self.writeRegister8(MC34X9_REG_FIFO_CTRL, self.CfgFifo)

        self.SetGerneralINTCtrl()

    #//Interrupt handler (clear interrupt flag)
    def INTHandler(self):
        value = 0

        value = self.readRegister8(MC34X9_REG_INTR_STAT)

        ptINT_Event = MC34X9_interrupt_event_t()
        ptINT_Event.r = value
        ptINT_Event.bTILT           = ((value >> 0) & 0x01)
        ptINT_Event.bFLIP           = ((value >> 1) & 0x01)
        ptINT_Event.bANYM           = ((value >> 2) & 0x01)
        ptINT_Event.bSHAKE          = ((value >> 3) & 0x01)
        ptINT_Event.bTILT_35        = ((value >> 4) & 0x01)

        value &= 0x40
        self.writeRegister8(MC34X9_REG_INTR_STAT, value)
        return ptINT_Event


    #//FIFO Interrupt handler (clear interrupt flag)
    def FIFOINTHandler(self):
        value = 0
        value = self.readRegister8(MC34X9_REG_FIFO_INTR)

        ptFIFO_INT_Event = MC34X9_fifo_interrupt_event_t()
        ptFIFO_INT_Event.r = value
        ptFIFO_INT_Event.bFIFO_EMPTY           = ((value >> 0) & 0x01)
        ptFIFO_INT_Event.bFIFO_FULL            = ((value >> 1) & 0x01)
        ptFIFO_INT_Event.bFIFO_THRESH          = ((value >> 2) & 0x01)
        return ptFIFO_INT_Event

    #//Get the range control  -> MC34X9_range_t
    def GetRangeCtrl(self):
        #// Read the data format register to preserve bits
        value = 0
        value = self.readRegister8(MC34X9_REG_RANGE_C)        
        r = value & 0x70
        r = (r >> 4)
        self.logger.debug("In GetRangeCtrl(): 0x{a:02X} -> {r}".format(a=value, r=r))
        return r
        

    #//Get the output sampling rate -> MC34X9_sr_t
    def GetSampleRate(self):
        #// Read the data format register to preserve bits
        value = 0
        value = self.readRegister8(MC34X9_REG_SR)
        self.logger.debug("In GetCWakeSampleRate(): 0x{a:02X}".format(a=value))
        value &= 0b00011111
        return value

    #//Is FIFO empty
    def IsFIFOEmpty(self):
        #// Read the data format register to preserve bits
        value = 0
        value = self.readRegister8(MC34X9_REG_FIFO_STAT)
        value &= 0x01
        #//self.logger.debug("FIFO_Status");
        #//self.logger.debug(value, HEX);

        if (value ^ 0x01):
            return False;	#//Not empty
        else:
            return True;  #//Is empty


    #//Read the raw counts and SI units measurement data
    def readRawAccel(self) -> MC34X9_acc_t:
        #//{2g, 4g, 8g, 16g, 12g}
        faRange = [ 19.614, 39.228, 78.456, 156.912, 117.684]
        #// 16bit
        faResolution = 32768.0

        rawData = bytearray(6)
        #// Read the six raw data registers into data array
        rawData = self.mcube_read_regs(MC34X9_REG_XOUT_LSB, 6)

        #print("Raw accel data: {nb} bytes -> '{r}'".format(nb=len(rawData), r=ubinascii.hexlify(rawData)))

        # Data is little-endian 16bit signed registers, so unpack accordingly
        (x,y,z) = struct.unpack("<hhh", rawData)        
        self.x = x
        self.y = y
        self.z = z
        
        self.AccRaw.XAxis = int(self.x)
        self.AccRaw.YAxis = int(self.y)
        self.AccRaw.ZAxis = int(self.z)
        self.AccRaw.XAxis_g = float(self.x) / faResolution * faRange[self.CfgRange]
        self.AccRaw.YAxis_g = float(self.y) / faResolution * faRange[self.CfgRange]
        self.AccRaw.ZAxis_g = float(self.z) / faResolution * faRange[self.CfgRange]

        return self.AccRaw




    def readRegister8(self, reg):
        value = self.mcube_read_regs(reg, 1)
        return value[0]


    def writeRegister8(self, reg, value):
        self.mcube_write_regs(reg, [value], 1)
        return


    #// ***BUS***
    #/** I2C init function */
    # def m_drv_i2c_init():
    #     Wire.begin()
    #     return 0


    #/** SPI init function */
    # def m_drv_spi_init(spi_hs_mode: e_m_drv_interface_spimode_t) -> int:
    #     #//Set active-low CS low to start the SPI cycle
    #     SPI.begin();
    #     SPI_SPEED_4M = 4000000
    #     SPI.beginTransaction(SPISettings(SPI_SPEED_4M, MSBFIRST, SPI_MODE3));
    #     return 0;


    #/** I2C/SPI read function */
    #/** bSpi : I2C/SPI bus selection.        SPI: 0,       I2C: 1           */
    #/** chip_select : Chip selection.        SPI: CS pins, I2C: I2C address */
    #/** reg : Sensor registers. */
    #/** value : read value.*/
    #/** size : data length */
    def mcube_read_regs(self, reg:int,  \
                        size:int):

        
        if not self.M_bSpi:  #//Reads an 8-bit register with the SPI port.
            value = bytearray(size)
            for i in range(size):
                value[i] = self._readRegister8(reg + i)
            return value
        else:
            #self.i2c.readfrom_mem_into(self.i2c_addr, register & 0xFF, self._buffer[0:length])
            buf = self.i2c.readfrom_mem(self.i2c_addr, reg & 0xFF, size)
            return buf


    #/** I2C/SPI write function */
    #/** bSpi : I2C/SPI bus selection.        SPI: 0,       I2C: 1           */
    #/** chip_select : Chip selection.        SPI: CS pins, I2C: I2C address */
    #/** reg : Sensor registers. */
    #/** li_values : List of values to write.*/
    #/** size : data length */
    def mcube_write_regs(self, reg: int,       \
                        li_values, size:int) -> int:

        for i in range(size):
            self._writeRegister8(reg + i, li_values[i])
        return 0


    #// Read 8-bit from register
    def _readRegister8(self, reg: int) -> int:
        value  = 0
        #/** 0 = SPI, 1 = I2C */
        if not self.M_bSpi:  #//Reads an 8-bit register with the SPI port.
            #/** SPI read function */
            #//Set active-low CS low to start the SPI cycle
            self.pin_cs.value(False)
            #//Send the register address
            self.spi.write(reg | 0x80)
            self.spi.write(0x00)
            #//Read the value from the register
            value = self.spi.read(1)
            #//Raise CS
            self.pin_cs.value(True)
        else:  #//Reads an 8-bit register with the I2C port.
            #/** I2C read function */
            buf = self.i2c.readfrom_mem(self.i2c_addr, reg & 0xFF, 1)
            return buf[0]

        return value


    #// Write 8-bit to register
    def _writeRegister8(self, reg:int, value:int):
        #/** 0 = SPI, 1 = I2C */
        if not self.M_bSpi:
            #//Set active-low CS low to start the SPI cycle
            self.pin_cs.value(False)
            #//Send the register address
            self.spi.write(reg)
            #//Send value to write into register
            self.spi.write(value)
            #//Raise CS
            self.pin_cs.value(True)
        else:
            value &= 0xff
            self.i2c.writeto_mem(self.i2c_addr, reg & 0xFF, bytearray([value]))          
        
        return
    

    #// ***MC34X9 driver motion part***
    def M_DRV_MC34X6_SetTFThreshold(self, threshold:int):
        _bFTThr = ( (threshold & 0x00ff), ((threshold & 0x7f00) >> 8 ), 0 )

        #// set threshold
        self._writeRegister8(MC34X9_REG_TF_THRESH_LSB, _bFTThr[0])
        self._writeRegister8(MC34X9_REG_TF_THRESH_MSB, _bFTThr[1])


    def M_DRV_MC34X6_SetTFDebounce(self, debounce: int):
        #// set debounce
        self._writeRegister8(MC34X9_REG_TF_DB, debounce)

    def M_DRV_MC34X6_SetANYMThreshold(self, threshold:int):
        _bANYMThr = ( (threshold & 0x00ff), ((threshold & 0x7f00) >> 8 ), 0)

        #// set threshold
        self._writeRegister8(MC34X9_REG_AM_THRESH_LSB, _bANYMThr[0])
        self._writeRegister8(MC34X9_REG_AM_THRESH_MSB, _bANYMThr[1])


    def M_DRV_MC34X6_SetANYMDebounce(self, debounce:int):
        self._writeRegister8(MC34X9_REG_AM_DB, debounce)


    def M_DRV_MC34X6_SetShakeThreshold(self, threshold:int):
        _bSHKThr = ((threshold & 0x00ff), ((threshold & 0xff00) >> 8 ), 0)

        #// set threshold
        self._writeRegister8(MC34X9_REG_SHK_THRESH_LSB, _bSHKThr[0])
        self._writeRegister8(MC34X9_REG_SHK_THRESH_MSB, _bSHKThr[1])


    def M_DRV_MC34X6_SetShake_P2P_DUR_THRESH(self, threshold: int,  shakeCount: int):

        _bSHKP2PDuration = ( (threshold & 0x00ff), ((threshold & 0x0f00) >> 8) | ((shakeCount & 0x7) << 4), 0)

        #// set peak to peak duration and count
        self._writeRegister8(MC34X9_REG_PK_P2P_DUR_THRESH_LSB, _bSHKP2PDuration[0])
        self._writeRegister8(MC34X9_REG_PK_P2P_DUR_THRESH_MSB, _bSHKP2PDuration[1])


    def M_DRV_MC34X6_SetTILT35Threshold(self, threshold: int):
        self.M_DRV_MC34X6_SetTFThreshold(threshold)


    def M_DRV_MC34X6_SetTILT35Timer(self, timer: int):
        value = 0

        value = self._readRegister8(MC34X9_REG_TIMER_CTRL)
        value &= 0b11111000
        value |= MC34X9_TILT35_DURATION_TIMER_t.MC34X9_TILT35_2p0

        self._writeRegister8(MC34X9_REG_TIMER_CTRL, timer)


    #// Tilt & Flip
    def _M_DRV_MC34X6_SetTilt_Flip(self):
        #// set threshold
        self.M_DRV_MC34X6_SetTFThreshold(s_bCfgFTThr)
        #// set debounce
        self.M_DRV_MC34X6_SetTFDebounce(s_bCfgFTDebounce)
        return


    #// AnyMotion
    def _M_DRV_MC34X6_SetAnym(self):
        #// set threshold
        self.M_DRV_MC34X6_SetANYMThreshold(s_bCfgANYMThr)

        #// set debounce
        self.M_DRV_MC34X6_SetANYMDebounce(s_bCfgANYMDebounce)
        return


    #// Shake
    def _M_DRV_MC34X6_SetShake(self):
        #// Config anymotion
        self._M_DRV_MC34X6_SetAnym()

        #// Config shake
        #// set threshold
        self.M_DRV_MC34X6_SetShakeThreshold(s_bCfgShakeThr)

        #// set peak to peak duration and count
        self.M_DRV_MC34X6_SetShake_P2P_DUR_THRESH(s_bCfgShakeP2PDuration, s_bCfgShakeCount)
        return


    #// Tilt 35
    def _M_DRV_MC34X6_SetTilt35(self):
        #// Config anymotion
        self._M_DRV_MC34X6_SetAnym()

        #// Config Tilt35
        #// set threshold
        self.M_DRV_MC34X6_SetTILT35Threshold(s_bCfgTILT35Thr)

        #//set timer
        self.M_DRV_MC34X6_SetTILT35Timer(MC34X9_TILT35_DURATION_TIMER_t.MC34X9_TILT35_2p0)
        return

    def sensorMotion(self, enableTILT, enableFLIP, enableANYM, enableSHAKE, enableTILT35):
        #//Enable motion feature and motion interrupt
        self.stop()
        self.SetSampleRate(MC34X9_sr_t.MC34X9_SR_DEFAULT_1000Hz)
        self.SetMotionCtrl(enableTILT, enableFLIP, enableANYM, enableSHAKE, enableTILT35)
        self.SetINTCtrl(enableTILT, enableFLIP, enableANYM, enableSHAKE, enableTILT35)
        self.wake()

        self.logger.debug("Sensor motion enable.")

    def sensorMotionThreshold(self, g):
        r = self.GetRangeCtrl()
        if r == MC34X9_range_t.MC34X9_RANGE_16G:
            _range = 16.0
        elif r == MC34X9_range_t.MC34X9_RANGE_12G:
            _range = 12.0
        elif r == MC34X9_range_t.MC34X9_RANGE_8G:
            _range = 8.0
        elif r == MC34X9_range_t.MC34X9_RANGE_4G:
            _range = 4.0
        elif r == MC34X9_range_t.MC34X9_RANGE_2G:
            _range = 2.0
        else:
            _range = 8.0
        
        #lsb = float(_range)/float(2**15)
        full_scale = float(2**15)-1
        v = int((float(g)/float(_range))*full_scale)
        if v>full_scale:
            v = int(full_scale)
        self.logger.debug("sensorMotionThreshold({g}) - Range = {r} -> SetANYMThreshold({v} = 0x{v:04x})".format(g=g, r=_range, v=v))


        self.M_DRV_MC34X6_SetANYMThreshold(v)


    def sensorImpactThreshold(self, th):
        
        if th != self._sensor_impact_th:
            self._sensor_impact_th = th
            self.logger.debug("MC3479: Change sensor impact threshold to {th}".format(th=th))
        
        self.sensorShakeThreshold(th)
        self.sensorMotion(enableTILT=False, enableFLIP=False, enableANYM=False, enableSHAKE=True, enableTILT35=False)
        self.sensorShakeThreshold(th)

    def sensorShakeThreshold(self, g):
        r = self.GetRangeCtrl()
        if r == MC34X9_range_t.MC34X9_RANGE_16G:
            _range = 16.0
        elif r == MC34X9_range_t.MC34X9_RANGE_12G:
            _range = 12.0
        elif r == MC34X9_range_t.MC34X9_RANGE_8G:
            _range = 8.0
        elif r == MC34X9_range_t.MC34X9_RANGE_4G:
            _range = 4.0
        elif r == MC34X9_range_t.MC34X9_RANGE_2G:
            _range = 2.0
        else:
            _range = 8.0
        
        #lsb = float(_range)/float(2**15)
        full_scale = float(2**16)-1
        v = int((float(g)/float(_range))*full_scale)
        if v>full_scale:
            v = int(full_scale)
        self.logger.debug("sensorShakeThreshold({g}) - Range = {r} -> M_DRV_MC34X6_SetShakeThreshold({v} = 0x{v:04x})".format(g=g, r=_range, v=v))


        self.M_DRV_MC34X6_SetShakeThreshold(v)

    def sensorFIFO(self, enableFifoThrINT):

        # //Enable FIFO and interrupt
        self.stop()
        self.SetSampleRate(MC34X9_sr_t.MC34X9_SR_50Hz)
        self.SetFIFOCtrl(MC34X9_fifo_ctl_t.MC34X9_FIFO_CTL_ENABLE, MC34X9_fifo_mode_t.MC34X9_FIFO_MODE_WATERMARK, FIFO_THRE_SIZE)
        self.SetFIFOINTCtrl(False, False, enableFifoThrINT); #//Enable FIFO threshold interrupt
        self.wake()

        self.logger.debug("Sensor FIFO enable.")



    def checkRange(self):
        r = self.GetRangeCtrl()
        if r == MC34X9_range_t.MC34X9_RANGE_16G:
            self.logger.debug("Range: +/- 16 g")
        elif r == MC34X9_range_t.MC34X9_RANGE_12G:
            self.logger.debug("Range: +/- 12 g")
        elif r == MC34X9_range_t.MC34X9_RANGE_8G:
            self.logger.debug("Range: +/- 8 g")
        elif r == MC34X9_range_t.MC34X9_RANGE_4G:
            self.logger.debug("Range: +/- 4 g")
        elif r == MC34X9_range_t.MC34X9_RANGE_2G:
            self.logger.debug("Range: +/- 2 g")
        else:
            self.logger.debug("Range: +/- ?? g")


    def checkSamplingRate(self):

        self.logger.debug("Low Power Mode SR")
        r = self.GetSampleRate()
        if r == MC34X9_sr_t.MC34X9_SR_25Hz:
            self.logger.debug("Output Sampling Rate: 25 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_50Hz:
            self.logger.debug("Output Sampling Rate: 50 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_62_5Hz:
            self.logger.debug("Output Sampling Rate: 62.5 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_100Hz:
            self.logger.debug("Output Sampling Rate: 100 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_125Hz:
            self.logger.debug("Output Sampling Rate: 125 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_250Hz:
            self.logger.debug("Output Sampling Rate: 250 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_500Hz:
            self.logger.debug("Output Sampling Rate: 500 Hz")
        elif r == MC34X9_sr_t.MC34X9_SR_DEFAULT_1000Hz:
            self.logger.debug("Output Sampling Rate: 1000 Hz")
        else:
            self.logger.debug("Output Sampling Rate: ?? Hz")

    async def readAndOutput(self):
        r = self.readRawAccel()
        self.logger.debug("MC3479 rawAccel = [{x}, {y}, {z}] counts -> g [{gx}, {gy}, {gz}] [m/s2]".format(x=r.XAxis,y=r.YAxis,z=r.ZAxis,gx=r.XAxis_g,gy=r.YAxis_g,gz=r.ZAxis_g))
        return r

    # // Interrupt checker: read interrupt register and determine if interrupt happen
    def interruptChecker(self):
        global enableFIFO

        retStr = []
        try:
            #// Init interrupt table
            retCode = False
            evt_mc34X9 = MC34X9_interrupt_event_t()
            fifo_evt_mc34X9 = MC34X9_fifo_interrupt_event_t()

            #// Read interrupt table
            fifo_evt_mc34X9 = self.FIFOINTHandler()
            evt_mc34X9 = self.INTHandler()

            #// Whether there is interrupt
            retCode |= evt_mc34X9.has_interrupt()
            retCode |= fifo_evt_mc34X9.has_interrupt()
            
            if retCode:
                self.logger.debug("Get interrupt: ")

            if enableFIFO:
                if fifo_evt_mc34X9.bFIFO_EMPTY:
                    retStr.append("FIFO empty. ")
                if fifo_evt_mc34X9.bFIFO_FULL:
                    retStr.append("FIFO full. ")
                if fifo_evt_mc34X9.bFIFO_THRESH:
                    retStr.append("FIFO threshold. ")


            if evt_mc34X9.bTILT:
                retStr.append("Tilt. ")
            
            if evt_mc34X9.bFLIP:
                retStr.append("Flip. ")

            if evt_mc34X9.bANYM:
                retStr.append("Any Motion. ")

            if evt_mc34X9.bSHAKE:
                retStr.append("Shake. ")

            if evt_mc34X9.bTILT_35:
                retStr.append("Tilt 35. ")

        except Exception as ex:
            self.logger.exc(ex, "Failed to check interrupts")
            
        return (retCode, ",".join(retStr))


