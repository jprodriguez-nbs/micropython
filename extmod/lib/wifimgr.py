
import gc
import micropython
import machine
import tools
print("WiFi Mgr")
tools.free(True)




import socket
import time
import network
import ure
import utime
from machine import WDT
import umdc_pinout as PINOUT
import uasyncio as asyncio

ap_ssid = "ud-umdc"
ap_password = "urbidermis"
ap_authmode = 3  # WPA2


wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

server_socket = None
connection_parameters = None

_logger = None
_display_text=[]

def logger():
    global _logger
    if _logger is None:
        import logging
        _logger = logging.getLogger("WIFI")
        _logger.setLevel(logging.DEBUG)
    return _logger

def get_connection_parameters():
    global connection_parameters
    return connection_parameters

def add_text(display_obj, t):
    global _display_text
    if display_obj is not None:
        _display_text.append(t)
        if len(_display_text)>5:
            _display_text.pop()
        display_obj.poweron()
        display_obj.fill(0)
        if _display_text is not None:
            n = len(_display_text)
            if n>0 and _display_text[0] is not None:
                display_obj.text(_display_text[0], 0, 0, 1)
            if n>1 and _display_text[1] is not None:
                display_obj.text(_display_text[1], 0, 12, 1)
            if n>2 and _display_text[2] is not None:
                display_obj.text(_display_text[2], 0, 24, 1)
            if n>3 and _display_text[3] is not None:
                display_obj.text(_display_text[3], 0, 36, 1)
            if n>4 and _display_text[4] is not None:
                display_obj.text(_display_text[4], 0, 48, 1)
        display_obj.show()

async def activate_wifi(display_obj = None):
    # Search WiFis in range
    if not wlan_sta.isconnected():
        logger().debug("Activate WLAN STA and SCAN ...")
        wlan_sta.active(False)
        await asyncio.sleep_ms(250)
        add_text(display_obj, "Activate WLAN STA")
        wlan_sta.active(True)
        await asyncio.sleep_ms(250)


async def get_connection(display_obj = None, start_web = False):
    """return a working WLAN(STA_IF) instance or None"""
    global connection_parameters
    global _display_text

    # First check if there already is any connection:
    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        await asyncio.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        logger().debug("Read WLAN profiles ...")
        add_text(display_obj, "Read profiles")

        # Read known network profiles from file
        profiles = read_profiles()

        networks = None

        try:
            await asyncio.wait_for(activate_wifi(display_obj), timeout = 3)
        except asyncio.TimeoutError:
            pass

        add_text(display_obj, "Scan WiFi")
        networks = wlan_sta.scan()
        
        if networks is not None and len(networks)>0:
            logger().debug("List found networks ...")
            AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
            for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
                ssid = ssid.decode('utf-8')
                if ssid in profiles:
                    encrypted = authmode > 0
                    logger().info("ssid: {ssid} chan: {chan} rssi: {rssi} authmode: {am}".format(ssid=ssid, chan=channel, rssi=rssi, am=AUTHMODE.get(authmode, '?')))
                    if encrypted:
                        if ssid in profiles:
                            password = profiles[ssid]
                            connected = await do_connect(display_obj, ssid, password)
                        else:
                            logger().debug("skipping unknown encrypted network")
                    else:  # open
                        connected = await do_connect(display_obj, ssid, None)
                    if connected:
                        try:
                            connection_parameters = (ssid, bssid, channel, rssi, authmode, hidden)
                            _display_text.clear()
                            _display_text.append("WLAN CONNECTED")
                            _display_text.append("{ssid}".format(ssid=ssid))
                            _display_text.append("RSSI: {rssi}".format(rssi=rssi))
                            add_text(display_obj,"Ch {c}".format(c=channel))
                        except Exception as ex:
                            print("Error updating display: {e}".format(e=str(ex)))
                            logger().exc(ex, "Error updating display")
                        break
        else:
            print("No WiFi networks found")

    except OSError as ex:
        logger().exc(ex, "failed to get connection")

    # start web server for connection manager:
    if not connected and start_web:
        print("WifiMgr.get_connection - start web app")
        connected = start()

    return wlan_sta if connected else None


def read_profiles():
    profiles = {}
    try:
        with open(PINOUT.NETWORK_PROFILES) as f:
            lines = f.readlines()
        for line in lines:
            if len(line)>0:
                try:
                    ssid, password = line.strip("\n").split(";")
                    profiles[ssid] = password
                except:
                    pass
    except:
        pass
    return profiles


def write_profiles(profiles):
    lines = []
    for ssid, password in profiles.items():
        lines.append("%s;%s\n" % (ssid, password))
    with open(PINOUT.NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


def update_wifi_cfg(ap_cfg, wifi_dat):
    global ap_ssid
    global ap_password
    
    try:
        if ap_cfg is not None:
            p = ap_cfg.split(";")
            ap_ssid = p[0]
            ap_password = p[1]
    except:
        pass

    try:
        if wifi_dat is not None:
            profiles = read_profiles()
            has_changed = False
            for line in wifi_dat:
                parts = line.split(";")
                p_ssid = parts[0]
                p_psw = parts[1]
                if p_ssid in profiles:
                    if p_psw != profiles[p_ssid]:
                        profiles[p_ssid] = p_psw
                        has_changed = True
                else:
                    profiles[p_ssid] = p_psw
                    has_changed = True
            if has_changed:
                write_profiles(profiles)            
    except:
        pass


async def do_connect(display_obj, ssid, password):
    wlan_sta.active(True)
    connected = wlan_sta.isconnected()
    if connected:
        return connected

    profiles = read_profiles()
    if ssid in profiles:
        logger().info('Trying to connect to {ssid}...'.format(ssid=ssid))
        add_text(display_obj, "Try {ssid}".format(ssid=ssid))
        wlan_sta.connect(ssid, password)
        for retry in range(100):
            connected = wlan_sta.isconnected()
            if connected:
                break
            #time.sleep(0.1)
            await asyncio.sleep_ms(100)
            #print('.', end='')
        if connected:
            add_text(display_obj, "OK {ssid}".format(ssid=ssid))
            logger().info('\nConnected. Network config: {c}'.format(c=wlan_sta.ifconfig()))
        else:
            add_text(display_obj, "FAILED {ssid}".format(ssid=ssid))
            logger().info('\nFailed. Not Connected to: {ssid}'.format(ssid=ssid))
    return connected


def send_header(client, status_code=200, content_length=None ):
    client.sendall("HTTP/1.0 {} OK\r\n".format(status_code))
    client.sendall("Content-Type: text/html\r\n")
    if content_length is not None:
        client.sendall("Content-Length: {}\r\n".format(content_length))
    client.sendall("\r\n")


def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        client.sendall(payload)
    client.close()

def get_ssids():
    wlan_sta.active(True)
    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    return ssids

def handle_root(client):
    wlan_sta.active(True)
    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    send_header(client)
    client.sendall("""\
        <html>
            <h1 style="color: #5e9ca0; text-align: center;">
                <span style="color: #ff0000;">
                    Wi-Fi Client Setup
                </span>
            </h1>
            <form action="configure" method="post">
                <table style="margin-left: auto; margin-right: auto;">
                    <tbody>
    """)
    while len(ssids):
        ssid = ssids.pop(0)
        client.sendall("""\
                        <tr>
                            <td colspan="2">
                                <input type="radio" name="ssid" value="{0}" />{0}
                            </td>
                        </tr>
        """.format(ssid))
    client.sendall("""\
                        <tr>
                            <td>Password:</td>
                            <td><input name="password" type="password" /></td>
                        </tr>
                    </tbody>
                </table>
                <p style="text-align: center;">
                    <input type="submit" value="Submit" />
                </p>
            </form>
            <p>&nbsp;</p>
            <hr />
            <h5>
                <span style="color: #ff0000;">
                    Your ssid and password information will be saved into the
                    "%(filename)s" file in your ESP module for future usage.
                    Be careful about security!
                </span>
            </h5>
            <hr />
        </html>
    """ % dict(filename=PINOUT.NETWORK_PROFILES))
    client.close()


async def handle_configure(client, request):
    match = ure.search("ssid=([^&]*)&password=(.*)", request)

    if match is None:
        send_response(client, "Parameters not found", status_code=400)
        return False
    # version 1.9 compatibility
    try:
        ssid = match.group(1).decode("utf-8").replace("%3F", "?").replace("%21", "!")
        password = match.group(2).decode("utf-8").replace("%3F", "?").replace("%21", "!")
    except Exception:
        ssid = match.group(1).replace("%3F", "?").replace("%21", "!")
        password = match.group(2).replace("%3F", "?").replace("%21", "!")

    if len(ssid) == 0:
        send_response(client, "SSID must be provided", status_code=400)
        return False

    r = await do_connect(None, ssid, password)
    if r:
        response = """\
            <html>
                <center>
                    <br><br>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP successfully connected to WiFi network %(ssid)s.
                        </span>
                    </h1>
                    <br><br>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}
        profiles[ssid] = password
        write_profiles(profiles)

        #time.sleep(5)
        await asyncio.sleep(5)

        return True
    else:
        response = """\
            <html>
                <center>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP could not connect to WiFi network %(ssid)s.
                        </span>
                    </h1>
                    <br><br>
                    <form>
                        <input type="button" value="Go back!" onclick="history.back()"></input>
                    </form>
                </center>
            </html>
        """ % dict(ssid=ssid)
        send_response(client, response)
        return False


def handle_not_found(client, url):
    send_response(client, "Path not found: {}".format(url), status_code=404)


def stop():
    global server_socket

    if server_socket:
        server_socket.close()
        server_socket = None

def activate_ap(port = 80):
    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]
    wlan_ap.active(True)
    wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)

    print('Connect to WiFi ssid ' + ap_ssid + ', default password: ' + ap_password)
    print('and access the ESP via your favorite web browser at 192.168.4.1.')
    print('Listening on:', addr)

async def start(port=80):
    global server_socket

    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

    stop()

    wlan_sta.active(True)
    activate_ap()

    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(1)

    ts_start = utime.time()

    if PINOUT.WDT_ENABLED:
        wdt = WDT(timeout=10000)

    while True:
        if wlan_sta.isconnected():
            return True

        ts_now = utime.time()
        elapsed_s = ts_now - ts_start
        if elapsed_s > 180:
            return False

        client, addr = server_socket.accept()
        print('client connected from', addr)
        try:
            client.settimeout(5.0)

            request = b""
            try:
                while "\r\n\r\n" not in request:
                    request += client.recv(512)
            except OSError:
                pass

            print("Request is: {}".format(request))
            if "HTTP" not in request:  # skip invalid requests
                continue

            # version 1.9 compatibility
            try:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).decode("utf-8").rstrip("/")
            except Exception:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).rstrip("/")
            print("URL is {}".format(url))

            if url == "":
                handle_root(client)
            elif url == "configure":
                await handle_configure(client, request)
            else:
                handle_not_found(client, url)

        finally:
            client.close()


        if PINOUT.WDT_ENABLED:
            wdt.feed()
