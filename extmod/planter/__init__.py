"""
import utime

debug = True

t_full = utime.ticks_us()


if debug:
    iname = "config"
    t = utime.ticks_us()
    print ("{n} ...".format(n=iname))

import planter.config as CFG

if debug:
    delta = utime.ticks_diff(utime.ticks_us(), t)
    print('Import {} Time = {:6.3f}ms'.format(iname, delta/1000))


if debug:
    iname = "status"
    t = utime.ticks_us()
    print ("{n} ...".format(n=iname))

from planter.status import *

if debug:
    delta = utime.ticks_diff(utime.ticks_us(), t)
    print('Import {} Time = {:6.3f}ms'.format(iname, delta/1000))


if debug:
    iname = "comm"
    t = utime.ticks_us()
    print ("{n} ...".format(n=iname))

from planter.comm import get_config, get_params, post_status_and_events

if debug:
    delta = utime.ticks_diff(utime.ticks_us(), t)
    print('Import {} Time = {:6.3f}ms'.format(iname, delta/1000))

if debug:
    iname = "core"
    t = utime.ticks_us()
    print ("{n} ...".format(n=iname))

from planter.core import *

if debug:
    delta = utime.ticks_diff(utime.ticks_us(), t)
    print('Import {} Time = {:6.3f}ms'.format(iname, delta/1000))


delta = utime.ticks_diff(utime.ticks_us(), t_full)
print('Import planter Time = {:6.3f}ms'.format(delta/1000))
"""
