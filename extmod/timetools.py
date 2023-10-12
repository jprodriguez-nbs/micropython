import time
import utime
import re

import logging
logger = logging.getLogger("timetools")
logger.setLevel(logging.DEBUG)

#DT_PATTERN = "\\s+(?=(\\d{2}(?:\\d{2})?)/(\\d{1,2})/(\\d{1,2})\\s+(\\d{1,2}):(\\d{1,2}):(\\d{1,2}).(\\d{1,3})"
DT_PATTERN = "(\d\d\d\d)[\/-](\d\d)[\/-](\d\d) *(\d\d):(\d\d):(\d\d).(\d\d\d)"
regex = re.compile(DT_PATTERN)

# 22/01/06,20:07:32+04
DT_GPRS_PATTERN ="(\d\d)[\/-](\d\d)[\/-](\d\d),(\d\d):(\d\d):(\d\d).(\d\d)"
re_gprs = re.compile(DT_GPRS_PATTERN)

def tuple2str(dt):
    ts_str = ""
    try:
        if len(dt)==8 or len(dt)==9:
            ts_str = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
        else:
            ts_str=dt[0]
    except Exception as ex:
        logger.exc(ex, "timetools.tuple2str failed: '{d}' -> {e}".format(d=str(dt), e=str(ex)))

    return ts_str

def str2tuple(ts_str):
    m = regex.match(ts_str)
    if m:
        # rtc -> (year, month, day, weekday, hours, minutes, seconds, subseconds)
        # embedded ports use epoch of 2000-01-01 00:00:00 UTC.
        # time -> (year, month, mday, hour, minute, second, weekday, yearday)
        t = (int(m.group(1)), int(m.group(2)), int(m.group(3)),int(m.group(4)), int(m.group(5)), int(m.group(6)), 0, 0)
    else:
        t = None
    return t

def grpsdt2tuple(ts_str):
    m = re_gprs.match(ts_str)
    if m:
        # rtc -> (year, month, day, weekday, hours, minutes, seconds, subseconds)
        # embedded ports use epoch of 2000-01-01 00:00:00 UTC.
        # time -> (year, month, mday, hour, minute, second, weekday, yearday)
        y = int(m.group(1))+2000
        t = (y, int(m.group(2)), int(m.group(3)),int(m.group(4)), int(m.group(5)), int(m.group(6)), 0, 0)
    else:
        t = None
    return t

def grpsdt2timestamp(d):
    t = grpsdt2tuple(d)
    ts = time.mktime(t)
    return ts

def totimestamp(d):
    ts = None
    try:
        if d is None:
            ts = 0
        elif isinstance(d, str):
            if d == "":
                ts = 0
            else:
                t = str2tuple(d)
                ts = time.mktime(t)
        elif isinstance(d, bytes):
            aux = d.decode('utf-8')
            if aux == "":
                ts = 0
            else:
                t = str2tuple(aux)
                ts = time.mktime(t)
        elif isinstance(d, tuple):
            if len(d)==8 or len(d)==9:
                t = d
            else:
                t = str2tuple(d[0])
            ts = time.mktime(t)                
        elif isinstance(d, int):
            ts = d
        
    except Exception as ex:
        logger.exc(ex, "timetools.totimestamp failed: '{d}' -> {e}".format(d=str(d), e=str(ex)))

    return ts

def tostr(d):
    try:
        if d is None:
            ts = ''
        elif isinstance(d, str):
            ts = d
        elif isinstance(d, bytes):
            ts = d.decode('utf-8')
        elif isinstance(d, tuple):
            if len(d)==8 or len(d)==9:
                ts = tuple2str(d)
            else:
                ts = d[0]
        elif isinstance(d, int):
            dt = time.localtime(d)
            # (year, month, mday, hour, minute, second, weekday, yearday)
            ts = "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[3],dt[4],dt[5],0)
    except Exception as ex:
        logger.exc(ex, "timetools.tostr failed: '{d}' -> {e}".format(d=str(d), e=str(ex)))      
    return ts

def diff_ts_s(ts_end_str, ts_start_str):
    if ts_end_str is not None and ts_start_str is not None and len(ts_end_str)>0 and len(ts_start_str)>0:
        ts_start = str2tuple(ts_start_str)
        ts_end = str2tuple(ts_end_str)

        dt_start = utime.mktime(ts_start)
        dt_end = utime.mktime(ts_end)
        time_diff_s = (dt_end-dt_start)
    else:
        time_diff_s = 0
    return time_diff_s


def diff_ts_ms(ts_end_str, ts_start_str):
    time_diff_s = diff_ts_s(ts_end_str, ts_start_str)
    elapsed_ms = time_diff_s * 1000
    return elapsed_ms

def diff_ts_h(ts_end_str, ts_start_str):
    time_diff_s = diff_ts_s(ts_end_str, ts_start_str)
    elapsed_h = float(time_diff_s) / 3600
    return elapsed_h