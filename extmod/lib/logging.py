import sys
import utime
import machine

import sys
import os
import io
import colors
import tools

CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10
NOTSET = 0

_level_dict = {
    CRITICAL: "CRIT",
    ERROR: "ERROR",
    WARNING: "WARNING",
    INFO: "INFO",
    DEBUG: "DEBUG",
}

_level_dict_color = {
    CRITICAL: "{c}CRIT{n}".format(c=colors.BOLD_PURPLE, n=colors.NORMAL),
    ERROR: "{c}ERROR{n}".format(c=colors.BOLD_RED, n=colors.NORMAL),
    WARNING: "{c}WARNING{n}".format(c=colors.BOLD_YELLOW, n=colors.NORMAL),
    INFO: "{c}INFO{n}".format(c=colors.BOLD_BLUE, n=colors.NORMAL),
    DEBUG: "DEBUG",
}

_stream = sys.stderr

_traces = []
_planter_id = ""

_webapp = None

_MAX_TRACES = 200

def set_webapp(webapp):
    global _webapp
    _webapp = webapp

def set_id(planter_id):
    global _planter_id
    _planter_id = planter_id


def clear_traces():
    global _traces
    _traces.clear()

def get_traces():
    global _traces
    return _traces

def _add_trace(**kwargs):
    global _traces
    """
    d = {
            "ts": dt,
            "id": _planter_id,
            "trace": msg
        }
    for k,v in kwargs.items():
        d[k]=v
    """
    _traces.append(kwargs)

    l = len(_traces)
    if l > _MAX_TRACES:
        # Remove excess of traces
        _traces = _traces[l-_MAX_TRACES:]


class LogRecord:
    def __init__(self):
        self.__dict__ = {}

    def __getattr__(self, key):
        return self.__dict__[key]


class Handler:
    def __init__(self):
        pass

    def setFormatter(self, fmtr):
        pass


class Logger:

    global _traces

    level = NOTSET
    handlers = []
    record = LogRecord()

    def __init__(self, name):
        self.name = name

    def _level_str(self, level):
        l = _level_dict.get(level)
        if l is not None:
            return l
        return "LVL%s" % level

    def _level_str_color(self, level):
        l = _level_dict_color.get(level)
        if l is not None:
            return l
        return "LVL%s" % level

    def setLevel(self, level):
        self.level = level

    def isEnabledFor(self, level):
        return level >= (self.level or _level)

    def log(self, level, msg, *args, **kwargs):
        if self.isEnabledFor(level):
            levelname = self._level_str(level)
            levelname_color = self._level_str_color(level)
            if args:
                try:
                    msg = msg % args
                except:
                    pass
            if self.handlers:
                d = self.record.__dict__
                d["levelname"] = levelname
                d["levelno"] = level
                d["message"] = msg
                d["name"] = self.name
                for h in self.handlers:
                    h.emit(self.record)
            else:
                ts = utime.time()
                dt = machine.RTC().datetime()
                if dt[0]>2020 or level>=INFO:
                    ts_str = "{}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}.{:03d}".format(dt[0],dt[1],dt[2],dt[4],dt[5],dt[6],int(dt[7]/1000))
                else:
                    ts_str = str(ts)
                tr = "{l}:{n}:{msg}".format(l=levelname_color, n=self.name, msg=msg)
                full_str = "{ts}:{tr}".format(ts=ts_str, tr=tr)
                #print(ts_str,":",tr, sep="", file=_stream)
                print(full_str, sep="", file=_stream)

                try:
                    if _webapp is not None:
                        #import webapp
                        #webapp.SendWSTrace(full_str)
                        _webapp.SendWSTrace(full_str)
                except:
                    pass

                if 'nopost' in  kwargs and kwargs['nopost']:
                    dopost = False
                else:
                    dopost = True

                if level>=INFO and dopost:
                    kwargs["level"]=levelname
                    kwargs["message"]=tools.remove_ascii_colors(msg)
                    kwargs["name"] = self.name
                    kwargs["ts"] = ts_str
                    kwargs["id"] = _planter_id
                    _add_trace(**kwargs)
                

    def debug(self, msg, *args):
        self.log(DEBUG, msg, *args)

    def info(self, msg, *args):
        self.log(INFO, msg, *args)

    def warning(self, msg, *args):
        self.log(WARNING, msg, *args)

    def error(self, msg, *args):
        self.log(ERROR, msg, *args)

    def critical(self, msg, *args):
        self.log(CRITICAL, msg, *args)

    def exc(self, e, msg, *args, **kwargs):
        s = io.StringIO()
        sys.print_exception(e, s)  
        self.log(ERROR, msg, *args, extradata=tools.remove_ascii_colors(s.getvalue()), **kwargs)
        sys.print_exception(e, _stream)    

    def exception(self, msg, *args):
        self.exc(sys.exc_info()[1], msg, *args)

    def addHandler(self, hndlr):
        self.handlers.append(hndlr)


_level = INFO
_loggers = {}


def getLogger(name="root"):
    if name in _loggers:
        return _loggers[name]
    l = Logger(name)
    _loggers[name] = l
    return l


def info(msg, *args):
    getLogger().info(msg, *args)


def debug(msg, *args):
    getLogger().debug(msg, *args)

def warn(msg, *args):
    getLogger().warn(msg, *args)

def error(msg, *args):
    getLogger().error(msg, *args)

def basicConfig(level=INFO, filename=None, stream=None, format=None):
    global _level, _stream
    _level = level
    if stream:
        _stream = stream
    if filename is not None:
        print("logging.basicConfig: filename arg is not supported")
    if format is not None:
        print("logging.basicConfig: format arg is not supported")
