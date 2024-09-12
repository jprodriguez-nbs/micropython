import struct
import nsClassWriter as nsClassWriter
import time
import gc
import os

import logging

_logger = logging.getLogger("NsDataClass")
_logger.setLevel(logging.DEBUG)

class NsDataClass(object):

    fields = ()
    # datetime string is 23 char: '2021/11/06 23:34:08.880'
    packstring = ''
    packlength = 0 #bytes

    def set_alarm_bit(self, alarm_bit):
        self.alarm = self.alarm | alarm_bit

    def reset_alarm_bit(self, alarm_bit):
        self.alarm = self.alarm & (0xFFFFFFFF ^ alarm_bit)

    def update_alarm(self, alarm_bit, value):
        old_value = self.alarm
        if value:
            self.set_alarm_bit(alarm_bit)
        else:
            self.reset_alarm_bit(alarm_bit)
        hasChanged = (old_value != self.alarm)
        return hasChanged


    def __init__(self, alarm=0):
        super(NsDataClass, self).__init__()
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
                result = int(l/cls.packlength)
                _logger.debug("File {fn} - length {l} bytes - packlength {packlength} -> {r} items".format(
                    fn=fn, l=l, packlength=cls.packlength, r=result
                ))
        except Exception as ex:
            _logger.exc(ex, "Failed to check nbitems_in_file '{fn}'".format(fn=fn))
            pass
        return result

    @classmethod
    def getlast_in_file(cls, fn):
        nb_items = int(cls.nbitems_in_file(fn))
        r = None
        if nb_items > 0:
            sw = nsClassWriter.StructWriter ()
            try:
                with open(fn, "rb") as f:
                    offset = (nb_items-1)*cls.packlength
                    f.seek(offset)
                    ba = f.read(cls.packlength)
                    obj = cls()
                    try:
                        sw.read(ba, obj)
                        r = obj
                    except Exception as ex:
                        _logger.exc(ex, "Failed read getlast_in_file '{fn}'".format(fn=fn))
                        pass
                    del(ba)
            except Exception as ex:  # open failed
                _logger.exc(ex, "Failed to getlast_in_file '{fn}'".format(fn=fn))

            gc.collect()
        return r

    @classmethod
    # Get the last items from the file, starting at initial_item
    # initial_item: Zero based item identifier
    def getsince_in_file(cls, fn, initial_item):
        nb_items = int(cls.nbitems_in_file(fn))
        r = []
        if nb_items > initial_item:
            sw = nsClassWriter.StructWriter ()
            try:
                with open(fn, "rb") as f:
                    offset = initial_item*cls.packlength
                    f.seek(offset)
                    nb_items_to_read = nb_items-initial_item
                    nb_bytes_to_read = nb_items_to_read*cls.packlength
                    ba = f.read(nb_bytes_to_read)
                    idx = 0
                    while idx < nb_bytes_to_read:
                        # Do stuff with byte.
                        obj = cls()
                        try:
                            sw.read(ba[idx:idx+cls.packlength], obj)
                            r.append(obj)
                        except Exception as ex:
                            _logger.exc(ex, "Failed read getsince_in_file '{fn}'".format(fn=fn))
                            pass
                        idx = idx + cls.packlength
                    del(ba)
            except Exception as ex:  # open failed
                _logger.exc(ex, "Failed to getlast_in_file '{fn}'".format(fn=fn))

            gc.collect()
        return r

    @classmethod
    def load_from_file(cls, fn):
        r = []
        sw = nsClassWriter.StructWriter ()
        try:
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
                    except Exception as ex:
                        _logger.exc(ex, "Failed read load_from_file '{fn}'".format(fn=fn))
                        pass
                    idx = idx + cls.packlength
                del(ba)
        except Exception as ex:  # open failed
            _logger.exc(ex, "Failed to load file '{fn}'".format(fn=fn))
        gc.collect()
        return r

    @staticmethod
    def append_to_file(fn, l):
        sw = nsClassWriter.StructWriter ()
        try:
            with open(fn, "ab") as f:
                for obj in l:
                    try:
                        ba = sw.write(obj)
                        f.write(ba)
                    except Exception as ex:  # open failed
                        _logger.exc(ex, "Failed to write in append_to_file '{fn}'".format(fn=fn))
        except Exception as ex:  # open failed
            _logger.exc(ex, "Failed to append_to_file '{fn}'".format(fn=fn))
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
