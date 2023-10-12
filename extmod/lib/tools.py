import sys
import usocket as socket
import uasyncio as asyncio
import re

import flashbdev
import uos as os
import gc
import os
import esp32
import micropython
import utime

import umdc_pinout as PINOUT
from constants import *
import colors

def get_parts(data):
    parts = None
    try:
        if data is None or len(data)<2:
            # Invalid length
            return None
        
        if isinstance(data, (bytes, bytearray)):
            data = data.decode('utf-8')
        
        if data[0] != '{' or data[-1] != '}':
            # Invalid brackets
            return None
        
        inner_data = data[1:-1]
        aux = inner_data.split(';')
        parts = [i.strip() for i in aux]
    except Exception as E:
        debug_msg = "tools.get_parts error: {e}".format(e=str(E))
        print(debug_msg)
        pass
    return parts


def check_mpy():
    sys_mpy = sys.implementation.mpy
    arch = [None, 'x86', 'x64',
        'armv6', 'armv6m', 'armv7m', 'armv7em', 'armv7emsp', 'armv7emdp',
        'xtensa', 'xtensawin'][sys_mpy >> 10]
    print('mpy version:', sys_mpy & 0xff)
    print('mpy flags:', end='')
    if arch:
        print(' -march=' + arch, end='')
    if sys_mpy & 0x100:
        print(' -mcache-lookup-bc', end='')
    if not sys_mpy & 0x200:
        print(' -mno-unicode', end='')
    print()

class test():
    # https://forum.micropython.org/viewtopic.php?t=3689
    #https://github.com/peterhinch/micropython-mqtt/blob/master/mqtt_as/mqtt_as.py
    # Check internet connectivity by sending DNS lookup to Google's 8.8.8.8
    """ async def wan_ok(self, packet = b'$\x1a\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01'):
        if not self.isconnected():  # WiFi is down
            return False
        length = 32  # DNS query and response packet size
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(False)
        s.connect(('8.8.8.8', 53))
        await asyncio.sleep(1)
        try:
            await self._as_write(packet, sock = s)
            await asyncio.sleep(2)
            res = await self._as_read(length, s)
            if len(res) == length:
                return True  # DNS response size OK
        except OSError:  # Timeout on read: no connectivity.
            return False
        finally:
            s.close()
        return False """


def remove_ascii_colors(s):
    result = re.sub('\033\\[[0-9]*;[0-9]*;[0-9]*m','', s)
    result = re.sub('\\\\\"\"','\\\"', result)
    result = re.sub('\\\\\"\"','\\\"', result)
    result = re.sub('"',"'", result)
    return result



def check_for_littlefs():
    from flashbdev import bdev
    buf = bytearray(16)
    bdev.readblocks(0, buf)
    return buf[8:16] == b"littlefs"

def detect_filesystem():
    buf = bytearray(16)
    flashbdev.bdev.readblocks(0, buf)
    if buf[3:8] == b'MSDOS':
        return 'FAT'
    if buf[8:16] == b"littlefs":
        return 'LITTLEFS'
    return 'unknown'


def check_flashdev():
    uname = os.uname()

    print(uname.machine, uname.release)
    print('MicroPython', uname.version)
    print()

    #print('flashbdev.size....:', flashbdev.size)
    print('reserved sectors..:', flashbdev.bdev.RESERVED_SECS)
    print('start sector......:', flashbdev.bdev.START_SEC)
    print('sector size.......:', flashbdev.bdev.SEC_SIZE)
    print('num blocks........:', flashbdev.bdev.NUM_BLK)


def filesystem_hex_dump(line_count=10, chunk_size=16):
    buf = bytearray(chunk_size)
    for block_num in range(line_count):
        offset = block_num * chunk_size
        print('%04x - %04x' % (offset, offset + chunk_size - 1), end=' - ')
        flashbdev.bdev.readblocks(block_num, buf)
        print(' '.join('%02x' % char for char in buf), end=' - ')
        print(''.join(chr(char) if 32 < char < 177 else '.' for char in buf))


def format_fs():
    os.umount('/')
    os.VfsLfs2.mkfs(flashbdev.bdev)
    os.mount(flashbdev.bdev, '/')

_ts_last_mem_check = 0
_last_free_mem = 0


def free(full=False):
    global _last_free_mem
    global _ts_last_mem_check
    gc.collect()
    
    su = micropython.stack_use()
    ts_now = utime.ticks_us()
    delta = utime.ticks_diff(ts_now, _ts_last_mem_check)
    _ts_last_mem_check = ts_now
    
    F = gc.mem_free()   # Free memory
    A = gc.mem_alloc()  # Allocated memory (used)
    T = F+A             # Total memory
    P = '{0:.2f}%'.format(F/T*100)  # Percentage free
    
    if F != _last_free_mem:
        full = True
        if _last_free_mem<F:
            c = colors.BOLD_GREEN
        else:
            c = colors.BOLD_RED
        print("Free memory has changed from {f_start} to {c}{f_end}{n}".format(c=c, n=colors.NORMAL, f_start=_last_free_mem, f_end=F))
        _last_free_mem = F
    
    if full:
        micropython.mem_info()
        esp32.idf_heap_info(esp32.HEAP_DATA)
        r= ('Total:{0} Free:{1} ({2}) - Stack use {3} - Elapsed since last check {4} [ms]'.format(T,F,P,su,delta/1000))
        print (r)
    return (T,F,A,su)

def df():
    s = os.statvfs('//')
    return ('{0} MB'.format((s[0]*s[3])/1048576))

def remove_messages_files(bRemove=True):
    
    if bRemove:
        try:
            os.remove(FN_STORED_MQTT_MESSAGES)
        except:
            pass

    try:
        with open(FN_STORED_MQTT_MESSAGES, "ab") as f:
            # Just create the file
            pass
    except:
        pass




def set_version(v):
    version_fn = "app/version.dat"
    with open(version_fn, 'w') as versionfile:
        versionfile.write(v)
        versionfile.close()

def get_version():
    version_fn = "app/version.dat"
    if 'version.dat' in os.listdir('app'):
        with open(version_fn) as f:
            version = f.read()
            return version
    return '0.0.0'

def ensure_data_files():
    remove_messages_files(False)

    
def file_or_dir_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False
    
def dir_exists(filename):
    try:
        return (os.stat(filename)[0] & 0x4000) != 0
    except OSError:
        return False
        
def file_exists(filename):
    try:
        return (os.stat(filename)[0] & 0x4000) == 0
    except OSError:
        return False

def remove_file(filename):
    if file_exists(filename):
        os.remove(filename)

def set_check_update():
    fn = "check_update.dat"
    if file_exists(fn) is False:
        with open(fn, 'w') as f:
            import utime
            ts_now = utime.time()
            f.write(str(ts_now))
            
def needs_to_check_update():
    return file_exists(FN_CHECK_UPDATE)

def do_reboot():
    # Soft reset using deepsleep to really release memory
    #machine.deepsleep(500)
    print("Reset to release all resources")
    from constants import FN_CHECK_UPDATE
    import network
    import utime
    remove_file(FN_CHECK_UPDATE)
    wlan_sta = network.WLAN(network.STA_IF)
    wlan_sta.active(False)
    utime.sleep(5)
    machine.reset()


def ping_payload(di_slave_ok):
    (T,F,A,su) = free(False)
    li_ping_payload = ['{ts};{T};{F};{A};{su}'.format(ts=utime.time(),T=T,F=F,A=A,su=su)]
    # slaves status
    for slave_id in di_slave_ok:
        is_ok = 1 if di_slave_ok[slave_id] else 0
        s ="{slave_id};{ok}".format(slave_id=slave_id, ok=is_ok)
        li_ping_payload.append(s)
    ping_payload = "{{{content}}}".format(content=';'.join(li_ping_payload))
    return ping_payload    