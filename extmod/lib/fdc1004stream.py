import sys
import utime

DIFFERENTIAL = False

class FDC1004:

    DELAY_BETWEEN_SAMPLES = 1000
    DO_SCAN = True
    FDC_ADDR = 80
    CAP_CFG = [0x0C, 0x0d, 0xff]  # 0 000 11 0 1 -> 300S/s, repeate enabled, all the enabled measurements are repeated
    ALL_REGISTERS = list(range(0x15)) + [0xFE, 0xFF]

    def write(self, reg, value):
        """Write value in device register"""
        seq = bytearray([reg, (value >> 8) & 0xFF, value & 0xFF])
        self.i2c_device.writeto(self.i2c_addr, seq)

    def read_reg(self, reg):
        """Return value from device register"""
        value = None
        try:
            self.data_in = self.i2c_device.readfrom_mem(self.i2c_addr, reg & 0xFF, 2)
            value = (self.data_in[0] << 8) | (self.data_in[1])
        except OSError:
            print("FAILED reading from register " + hex(reg))
            raise
        return value
        
        

    def data_bin(self):
        msb = bin(self.data_in[0])[2:]
        lsb = bin(self.data_in[1])[2:]
        msb = "0" * (8-len(msb)) + msb
        lsb = "0" * (8-len(lsb)) + lsb
        return msb + " " + lsb

    def data_hex(self):
        msb = hex(self.data_in[0])[2:]
        lsb = hex(self.data_in[1])[2:]
        msb = "0" * (2-len(msb)) + msb
        lsb = "0" * (2-len(lsb)) + lsb
        return "0x" + msb + lsb

    def data_dec(self):
        return self.data_in[0] * 256 + self.data_in[1]

    def regscan(self, registers=None, do_print=False):
        if registers is None:
            registers = FDC1004.ALL_REGISTERS
        for idx, pointerregister in enumerate(registers):
            self.read_reg(pointerregister)
            if do_print:
                s = \
                    "\t" + \
                    str(hex(pointerregister)) + ": " + \
                    self.data_bin() + " = " + \
                    self.data_hex() + " = " + \
                    str(self.data_dec())
                print(s)

    def get_cap_code(self, channel):
        the_bytes = [0, 0, 0, 0]
        msb_reg = channel << 1
        lsb_reg = msb_reg + 1
        self.read_reg(msb_reg)
        the_bytes[0:2] = list(self.data_in)
        self.read_reg(lsb_reg)
        the_bytes[2:4] = list(self.data_in)
        
        result = \
            the_bytes[0] * (2**24) + \
            the_bytes[1] * (2**16) + \
            the_bytes[2] * (2**8) + \
            the_bytes[3]
            
        return result

    def get_cap(self, channel):
        code = self.get_cap_code(channel)

        # Discard 8 lowest bits
        code >>= 8

        # Get two's complement for the remaining 24-bit value
        mask = 2 ** (24 - 1)
        twos_comp = -(code & mask) + (code & ~mask)

        # That value divided by 2^19 is the capacitance in pF
        result = twos_comp / (2**19)
        return result

    def setup(self):

        #
        # Connection to implement OoP method
        #
        # CIN1 -> Level electrode
        # CIN2 -> Reference Liquid electrode (RL)
        # CIN3 -> Reference Environment electrode (RE)
        # CIN4 -> Floating, no electrode attached
        #
        # Measurements configuration
        # MEAS1 = CIN1 (CHA) – CIN4 (CHB).
        #   CIN1 is set as the positive input channel, 
        #   and CIN4 is set as the negative input channel.
        # MEAS2 = CIN2 (CHA) – CIN4 (CHB). 
        #   CIN2 is set as the positive input channel, 
        #   and CIN4 is set as the negative input channel.
        #

        if DIFFERENTIAL is False:
            # Original
            setup_sequence = (
                ("Reset", [0x0C, 0x80, 0x00]),
                #("Measurement 1", [0x08, 0x1c, 0x00]),  # 000 111 00 -> CHA1 = CIN1, CHA2 = Disabled, 15*3.125 pF offset
                ("Measurement 1", [0x08, 0x10, 0x40]),  # 000 100 00 -> CHA1 = CIN1, CHA2 = Capdac, *3.125 pF offset
                ("Measurement 2", [0x09, 0x3c, 0x00]),  # 001 111 00 -> CHA1 = CIN2, CHA2 = Disabled
                ("Measurement 3", [0x0a, 0x5c, 0x00]),  # 010 111 00 -> CHA1 = CIN3, CHA2 = Disabled
                ("Measurement 4", [0x0b, 0x7c, 0x00]),  # 011 111 00 -> CHA1 = CIN4, CHA2 = Disabled
                ("Cap config", FDC1004.CAP_CFG),
                
                #("Offset CAL 1", [0x0D, 0xFF, 0xFF]),  # 111 110 00 -> -15 pF
                ("Offset CAL 1", [0x0D, 0x00, 0x00]),  # 0
            )
        else:
            setup_sequence = (
                ("Reset", [0x0C, 0x80, 0x00]),
                ("Measurement 1", [0x08, 0x0c, 0x00]),  # 000 011 00 -> CHA1 = CIN1, CHA2 = CIN4
                ("Measurement 2", [0x09, 0x2c, 0x00]),  # 001 011 00 -> CHA1 = CIN2, CHA2 = CIN4
                ("Measurement 3", [0x0a, 0x4c, 0x00]),  # 010 011 00 -> CHA1 = CIN3, CHA2 = CIN4
                #("Measurement 4", [0x0b, 0x7c, 0x00]),  # 011 111 00 -> CHA1 = CIN4, CHA2 = Disabled
                
                
                
                # 0x0d = 0 000 11 0 1 -> 400S/s, repeate enabled, all the enabled measurements are repeated
                # 0xee = 1110 1110 -> measurement 1, 2 and 3 enabled
                ("Cap config", [0x0C, 0x0d, 0xee]  ),   
                
                ("Offset CAL 1", [0x0D, 0xFF, 0xFF]),  # 111 110 00 -> -15 pF
                
            )

        # Make sure it is ready
        
        if FDC1004.DO_SCAN:
            while True:            
                slaves = self.i2c_device.scan()
                print("I2C device addresses: " + ", ".join([str(slave) for slave in slaves]))
                if not self.i2c_addr in slaves:
                    check_ready = False
                    print("FDC is not ready.")
                else:
                    print("FDC is ready.")
                    break
                    
                utime.sleep_ms(1000)

        # Setup
        print("Starting setup:")
        for cmd in setup_sequence:
            print("\t" + cmd[0])
            self.i2c_device.writeto(self.i2c_addr, bytearray(cmd[1]))            
            
        print("Setup done")

        # Do checks
        print("Starting checks")
        self.regscan(do_print=True)


   
    def __init__(self, i2c_bus, i2c_addr = FDC_ADDR):
        self.i2c_device = i2c_bus
        self.i2c_addr = i2c_addr
        self.data_in = bytearray(2)
        self.setup()


def test_fdc1004(i2c=None):
    print("Starting streaming")
    
    import machine
    import planter_pinout as PINOUT
    import logging
    
    _logger = logging.getLogger("test")
    _logger.setLevel(logging.DEBUG)
    
    if i2c is None:
        i2c = machine.SoftI2C(scl=machine.Pin(PINOUT.I2C_SCL), sda=machine.Pin(PINOUT.I2C_SDA),freq=400000)
    
    r = i2c.scan()
    _logger.debug("I2C SCAN: {r}".format(r=r))
    
    fdc1004 = FDC1004(i2c)
    
    level = None
    
    while True:
        if FDC1004.DELAY_BETWEEN_SAMPLES:
            utime.sleep_ms(FDC1004.DELAY_BETWEEN_SAMPLES)
            
        c_level_fF = fdc1004.get_cap(0)*1000
        c_reference_liquid_fF = fdc1004.get_cap(1)*1000
        c_reference_environment_fF = fdc1004.get_cap(2)*1000

        href = 100
        
        if DIFFERENTIAL:
        
            #c_level_0_fF = 7840
            c_level_0_fF = 15000
            

            d = (c_reference_environment_fF-c_reference_liquid_fF)
            if d!=0:
                level = href*(c_level_fF-c_level_0_fF)/d
            else:
                level = None
        else:
            c_level_0_fF = 0
            c_range = 10000-c_level_0_fF
            n_level = href*(c_level_fF-c_level_0_fF)/c_range
            if level is None:
                level = n_level
            else:
                level = level*0.95 + n_level*0.05
        
        msg = "C Level = {cl:.01f} fF, C reference liquid = {crl:.01f} fF, C reference environment = {cre:.01f} fF -> Level = {l:.01f} ".format(
            cl=c_level_fF, crl=c_reference_liquid_fF, cre=c_reference_environment_fF, l=level
        )
        print(msg)
   

if __name__ == "__main__":
    test_fdc1004(None)