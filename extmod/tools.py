import sys
import usocket as socket
import uasyncio as asyncio
import re

import flashbdev
import uos as os
import gc
import os

import planter_pinout as PINOUT

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

def free(full=False):
    gc.collect()
    F = gc.mem_free()
    A = gc.mem_alloc()
    T = F+A
    P = '{0:.2f}%'.format(F/T*100)
    if not full: return P
    else : return ('Total:{0} Free:{1} ({2})'.format(T,F,P))

def df():
    s = os.statvfs('//')
    return ('{0} MB'.format((s[0]*s[3])/1048576))

def remove_irrigation_files(bRemove=True):
    
    if bRemove:
        try:
            os.remove(PINOUT.IRRIGATION_DATA_FN)
        except:
            pass

        try:
            os.remove(PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN)
        except:
            pass

    try:
        with open(PINOUT.IRRIGATION_DATA_FN, "ab") as f:
            # Just create the file
            pass
    except:
        pass

    try:
        with open(PINOUT.IRRIGATION_COMMUNICATION_REGISTER_FN, "ab") as f:
            # Just create the file
            pass
    except:
        pass


def remove_rain_files(bRemove=True):
    
    if bRemove:
        try:
            os.remove(PINOUT.RAIN_DATA_FN)
        except:
            pass

        try:
            os.remove(PINOUT.RAIN_COMMUNICATION_REGISTER_FN)
        except:
            pass

    try:
        with open(PINOUT.RAIN_DATA_FN, "ab") as f:
            # Just create the file
            pass
    except:
        pass

    try:
        with open(PINOUT.RAIN_COMMUNICATION_REGISTER_FN, "ab") as f:
            # Just create the file
            pass
    except:
        pass

def remove_data_files():
    try:
        os.remove('measures.dat')
    except:
        pass

    remove_irrigation_files()
    remove_rain_files()


def set_version(v):
    version_fn = "app/version.dat"
    with open(version_fn, 'w') as versionfile:
        versionfile.write(v)
        versionfile.close()



def ensure_data_files():
    remove_irrigation_files(False)
    remove_rain_files(False)

