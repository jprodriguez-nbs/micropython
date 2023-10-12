import nsClassWriter
try:
    import timetools
except:
    from ..nsUtilidades import nsuTime as timetools

import gc
try:
    import ubinascii
    from ubinascii import a2b_base64 as b64decode
    from ubinascii import b2a_base64 as b64encode
except:
    import base64
    from base64 import b64decode as b64decode
    from base64 import b64encode as b64encode

from nsDataClass import NsDataClass
from nsPlanterPowerData import Power3ChData, Power1ChData


class PowerTimeSeries(object):

    KEY_TYPE = "type"
    KEY_CHANNELS = "channels"
    KEY_DATA = "data"
    KEY_REF_MS = "ref_ms"
    KEY_REF_TS = "ref_ts"
    KEY_SERIES = "series"

    def __init__(self, reference_ms, reference_ts):
        super(PowerTimeSeries, self).__init__()
        self._series = {}
        self._reference_ms = reference_ms
        self._reference_ts = reference_ts

    def add_serie(self, name, datatype, channels):
        if name not in self._series:
            self._series[name] = {
                PowerTimeSeries.KEY_TYPE: datatype,
                PowerTimeSeries.KEY_CHANNELS: channels,
                PowerTimeSeries.KEY_DATA: []
            }

    def add_data(self, name, data):
        if name not in self._series:
            # Cannot add
            return False
        self._series[name][PowerTimeSeries.KEY_DATA].append(data)
        return True

    def add_list(self, name, l):
        if name not in self._series:
            # Cannot add
            return False
        self._series[name][PowerTimeSeries.KEY_DATA] = self._series[name][PowerTimeSeries.KEY_DATA] + l
        return True

    def series(self):
        return self._series

    def to_dict(self):
        r = {
            PowerTimeSeries.KEY_REF_MS: self._reference_ms,
            PowerTimeSeries.KEY_REF_TS: self._reference_ts,
            PowerTimeSeries.KEY_SERIES: {}
        }
        sw = nsClassWriter.StructWriter()
        for name in self._series:
            s = self._series[name]
            datatype = s[PowerTimeSeries.KEY_TYPE]
            channels = s[PowerTimeSeries.KEY_CHANNELS]
            data = s[PowerTimeSeries.KEY_DATA]

            packlength = datatype.packlength
            nb_elements = len(data)
            nb_bytes = nb_elements * packlength
            databytes_ba = bytearray(nb_bytes)
            for idx in range(len(data)):
                item = data[idx]
                databytes_ba[idx*packlength:(idx+1)
                             * packlength] = sw.write(item)
            databytes_b64 = b64encode(databytes_ba)

            s_dict = {
                PowerTimeSeries.KEY_TYPE: datatype.__name__,
                PowerTimeSeries.KEY_CHANNELS: channels,
                PowerTimeSeries.KEY_DATA: databytes_b64
            }

            r[PowerTimeSeries.KEY_SERIES][name] = s_dict

        return r

    def from_dict(self, d):
        sw = nsClassWriter.StructWriter()
        self._series = {}
        if d is None:
            return
        self._reference_ms = d[PowerTimeSeries.KEY_REF_MS]
        self._reference_ts = d[PowerTimeSeries.KEY_REF_TS]
        d_series = d[PowerTimeSeries.KEY_SERIES]
        for name in d_series:
            s = d_series[name]
            datatype = s[PowerTimeSeries.KEY_TYPE]
            channels = s[PowerTimeSeries.KEY_CHANNELS]
            data = s[PowerTimeSeries.KEY_DATA]
            li_obj = []

            if "Power3ChData" in datatype:
                cls = Power3ChData
            elif "Power1ChData" in datatype:
                cls = Power1ChData
            else:
                # Cannot process
                continue

            packlength = cls.packlength
            iDecodedData = b64decode(data)
            nb_elements = int(len(iDecodedData)/packlength)
            for idx in range(nb_elements):
                obj = cls()
                try:
                    sw.read(
                        iDecodedData[idx*cls.packlength:(idx+1)*cls.packlength], obj)
                    li_obj.append(obj)
                except:
                    pass

            s_dict = {
                PowerTimeSeries.KEY_TYPE: cls,
                PowerTimeSeries.KEY_CHANNELS: channels,
                PowerTimeSeries.KEY_DATA: li_obj
            }

            self._series[name] = s_dict

    @staticmethod
    def test1():
        try:
            import machine
            import utime

            rtc = machine.RTC()
            dt = rtc.datetime()
            ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(
                dt[0], dt[1], dt[2], dt[4], dt[5], dt[6], int(dt[7]/1000))
            ticks_ms = utime.ticks_ms()
            reference_ts = utime.time()
        except:
            import time
            ticks_ms = 3678
            reference_ts = time.time()

        pts = PowerTimeSeries(reference_ms = 100, reference_ts = reference_ts)
        pts.add_serie("main", Power3ChData, ["pv", "batt", "12v"])

        obj1 = Power3ChData(ticks_ms, 12.04, 1.26, 12.43, 0.750, 18.28, 0.53)
        obj2 = Power3ChData(ticks_ms, 12.14, 1.23, 12.42, 0.730, 18.20, 0.51)
        pts.add_data("main", obj1)
        pts.add_data("main", obj2)

        pts.add_serie("backup", Power1ChData, ["cell"])
        obj3 = Power1ChData(ticks_ms, 3.67, 0.23)
        obj4 = Power1ChData(ticks_ms, 3.63, 0.21)
        pts.add_data("backup", obj3)
        pts.add_data("backup", obj4)

        d = pts.to_dict()
        print("Dictionary: {d}".format(d=str(d)))

        pts2 = PowerTimeSeries(reference_ms = 100, reference_ts = reference_ts)
        pts2.from_dict(d)

        print("PTS2: {s}".format(s=str(pts2)))

        pts2_s = pts2.series()
        for name in pts2_s:
            s = pts2_s[name]
            print("Serie: {name}, {t}, channels {c}, ref_ms {ref_ms}, ref_ts {ref_ts}:".format(
                name=name, t=str(s[PowerTimeSeries.KEY_TYPE].__name__), c=s[PowerTimeSeries.KEY_CHANNELS], 
                ref_ms=d[PowerTimeSeries.KEY_REF_MS], ref_ts=d[PowerTimeSeries.KEY_REF_TS]))
            for item in s["data"]:
                print("  - {i}".format(i=str(item)))
