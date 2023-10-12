import time

from pn532.nfc.pn532_log import DMSG

from pn532.interfaces.pn532Interface import Pn532Interface, PN532_PREAMBLE, PN532_STARTCODE1, PN532_STARTCODE2, PN532_HOSTTOPN532, \
    PN532_INVALID_FRAME, PN532_POSTAMBLE, PN532_PN532TOHOST, PN532_ACK_WAIT_TIME, PN532_TIMEOUT, \
    PN532_INVALID_ACK

PN532_I2C_ADDRESS =  (0x48 >> 1)

class Pn532I2c(Pn532Interface):
    RPI_BUS0 = 0
    RPI_BUS1 = 1

    def __init__(self, i2c_device):
        self._wire = i2c_device
        self._command = 0

    def begin(self):
        time.sleep(1)

    def wakeup(self):
        time.sleep(.05) # wait for all ready to manipulate pn532
        b = b'\x00'
        return self._wire.writeto(PN532_I2C_ADDRESS, b)

    def writeCommand(self, header: bytearray, body: bytearray = bytearray()):
        self._command = header[0]
        data_out = [PN532_PREAMBLE, PN532_STARTCODE1, PN532_STARTCODE2]

        length = len(header) + len(body) + 1 # length of data field: TFI + DATA
        data_out.append(length)
        data_out.append((~length & 0xFF) + 1) # checksum of length

        data_out.append(PN532_HOSTTOPN532)
        dsum = PN532_HOSTTOPN532 + sum(header) + sum(body)  # sum of TFI + DATA

        data_out += list(header)
        data_out += list(body)
        checksum = ((~dsum & 0xFF) + 1) & 0xFF # checksum of TFI + DATA

        data_out += [checksum, PN532_POSTAMBLE]

        DMSG("writeCommand: header {}   body {}   data {}".format(header, body, data_out))

        try:
            # send data
            self._wire.writeto(PN532_I2C_ADDRESS, bytes(data_out))
        except Exception as e:
            DMSG(e)
            DMSG("\nToo many data to send, I2C doesn't support such a big packet\n")  # I2C max packet: 32 bytes
            return PN532_INVALID_FRAME

        return self._readAckFrame()

    def _getResponseLength(self, timeout: int):
        PN532_NACK = [0, 0, 0xFF, 0xFF, 0, 0]
        timer = 0
        PN532_NACK_bytes = bytes(PN532_NACK)

        while 1:
            responses = self._wire.readfrom(PN532_I2C_ADDRESS, 6)
            if len(responses)>0:
                #data = bytearray(responses[0])
                data = responses
                
                DMSG('_getResponseLength length frame: {!r}'.format(data))
                if data[0] & 0x1:
                # check first byte --- status
                    break # PN532 is ready

            time.sleep(.001)    # sleep 1 ms
            timer+=1
            if ((0 != timeout) and (timer > timeout)):
                return -1


        if (PN532_PREAMBLE != data[1] or # PREAMBLE
            PN532_STARTCODE1 != data[2] or # STARTCODE1
            PN532_STARTCODE2 != data[3]    # STARTCODE2
        ):
            DMSG('Invalid Length frame: {}'.format(data))
            return PN532_INVALID_FRAME

        length = data[4]
        DMSG('_getResponseLength length is {:d}'.format(length))

        # request for last respond msg again
        DMSG('_getResponseLength writing nack: {!r}'.format(PN532_NACK))
        self._wire.writeto(PN532_I2C_ADDRESS, PN532_NACK_bytes)

        return length

    def readResponse(self, timeout: int = 1000): # -> (int, bytearray):
        t = 0
        length = self._getResponseLength(timeout)
        buf = bytearray()

        if length < 0:
            return length, buf

        # [RDY] 00 00 FF LEN LCS (TFI PD0 ... PDn) DCS 00
        while 1:
            responses = self._wire.readfrom(PN532_I2C_ADDRESS, 6 + length + 2)
            if len(responses)>0:
                #data = bytearray(responses[0])
                data = responses
                if (data[0] & 1):
                # check first byte --- status
                    break # PN532 is ready

            time.sleep(.001)     # sleep 1 ms
            t+=1
            if ((0 != timeout) and (t> timeout)):
                return -1, buf

        if (PN532_PREAMBLE != data[1] or # PREAMBLE
            PN532_STARTCODE1 != data[2] or # STARTCODE1
            PN532_STARTCODE2 != data[3]    # STARTCODE2
        ):
            DMSG('Invalid Response frame: {}'.format(data))
            return PN532_INVALID_FRAME, buf

        length = data[4]

        if (0 != (length + data[5] & 0xFF)):
         # checksum of length
            DMSG('Invalid Length Checksum: len {:d} checksum {:d}'.format(length, data[5]))
            return PN532_INVALID_FRAME, buf

        cmd = self._command + 1 # response command
        if (PN532_PN532TOHOST != data[6] or (cmd) != data[7]):
            return PN532_INVALID_FRAME, buf

        length -= 2

        DMSG("readResponse read command:  {:x}".format(cmd))

        dsum = PN532_PN532TOHOST + cmd
        buf = data[8:-2]
        DMSG('readResponse response: {!r}\n'.format(buf))
        dsum += sum(buf)

        checksum = data[-2]
        if (0 != (dsum + checksum) & 0xFF):
            DMSG("checksum is not ok: sum {:d} checksum {:d}\n".format(dsum, checksum))
            return PN532_INVALID_FRAME, buf
        # POSTAMBLE data [-1]

        return length, buf

    def _readAckFrame(self) -> int:
        PN532_ACK = [0, 0, 0xFF, 0, 0xFF, 0]

        DMSG("wait for ack at : ")
        DMSG(time.time())
        DMSG('\n')

        t = 0
        while 1:
            responses = self._wire.readfrom(PN532_I2C_ADDRESS, len(PN532_ACK) + 1)
            if len(responses)>0:
                #data = bytearray(responses[0])
                data = responses
                if (data[0] & 1):
                # check first byte --- status
                    break # PN532 is ready

            time.sleep(.001)    # sleep 1 ms
            t+=1
            if (t > PN532_ACK_WAIT_TIME):
                DMSG("Time out when waiting for ACK\n")
                return PN532_TIMEOUT

        DMSG("ready at : ")
        DMSG(time.time())
        DMSG('\n')

        ackBuf = list(data[1:])

        if ackBuf != PN532_ACK:
            DMSG("Invalid ACK {}\n".format(ackBuf))
            return PN532_INVALID_ACK

        return 0
