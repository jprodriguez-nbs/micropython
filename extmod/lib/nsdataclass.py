from micropython import const
import struct
import nsClassWriter
import time
import timetools
import gc
import os

class NsDataClass():

    fields = ()
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    packstring = ''
    packlength = 0 #bytes

    def set_alarm_bit(self, alarm_bit):
        self.alarm = self.alarm | alarm_bit

    def reset_alarm_bit(self, alarm_bit):
        self.alarm = self.alarm & (0xFFFFFFFF ^ alarm_bit)

    def update_alarm(self, alarm_bit, value):
        if value:
            self.set_alarm_bit(alarm_bit)
        else:
            self.reset_alarm_bit(alarm_bit)


    def __init__(self, alarm=0):
        self.alarm = alarm


    def __str__(self):
        return str(self.to_dict())

    def to_dict(self):
        d = {}
        return d

    @classmethod
    def nbitems_in_file(cls, fn):
        result = 0
        try:
            data = os.stat(fn)
            if data is not None:
                l = data[6]
                result = l/cls.packlength
        except:
            pass
        return result

    @classmethod
    def getlast_in_file(cls, fn):
        nb_items = cls.nbitems_in_file(fn)
        r = None
        if nb_items > 0:
            sw = nsClassWriter.StructWriter ()
            with open(fn, "rb") as f:
                offset = (nb_items-1)*cls.packlength
                f.seek(offset)
                ba = f.read(cls.packlength)
                obj = cls()
                try:
                    sw.read(ba, obj)
                    r = obj
                except:
                    pass
                del(ba)
            gc.collect()
        return r

    @classmethod
    def load_from_file(cls, fn):
        r = []
        sw = nsClassWriter.StructWriter ()
        with open(fn, "rb") as f:
            ba = f.read()
            lf = len(ba)
            nb_items = lf/cls.packlength
            idx = 0
            while idx < lf:
                # Do stuff with byte.
                obj = cls()
                try:
                    sw.read(ba[idx:idx+cls.packlength], obj)
                    r.append(obj)
                except:
                    pass
                idx = idx + cls.packlength
            del(ba)
        gc.collect()
        return r

    @staticmethod
    def append_to_file(fn, l):
        sw = nsClassWriter.StructWriter ()
        with open(fn, "ab") as f:
            for obj in l:
                ba = sw.write(obj)
                f.write(ba)
        gc.collect()


    @classmethod
    def to_ba(cls):
        sw = nsClassWriter.StructWriter()
        ba = sw.write(cls)
        return ba

    @classmethod
    def from_ba(cls, ba):
        sw = nsClassWriter.StructWriter()
        sw.read(ba, cls)
