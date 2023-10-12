import usocket, os, gc

import logging
import utime
import hwversion

_logger = logging.getLogger("Utils.HttpClient")
_logger.setLevel(logging.INFO)

WDT_ENABLED = hwversion.WDT_ENABLED
if WDT_ENABLED:
    import machine
    _wdt = machine.WDT(timeout=240000)

class Response:

    def __init__(self, socket, saveToFile=None):
        self.status_code = None
        self.c = None
        self.reason = None
        self._socket = socket
        self._saveToFile = saveToFile
        self._encoding = 'utf-8'
        if saveToFile is not None:
            CHUNK_SIZE = 512 # bytes
            with open(saveToFile, 'w') as outfile:
                data = self._socket.read(CHUNK_SIZE)
                while data:
                    outfile.write(data)
                    data = self._socket.read(CHUNK_SIZE)
                outfile.close()
                
            self.close()

    def close(self):
        if self._socket:
            self._socket.close()
            self._socket = None

    @property
    def content(self):
        if self._saveToFile is not None:
            raise SystemError('You cannot get the content from the response as you decided to save it in {}'.format(self._saveToFile))

        result = None
        if self._socket is not None:
            try:
                self.c = self._socket.read()
                result = self.c
            finally:
                self.close()
        else:
            result = self.c
        return result

    @property
    def text(self):
        return str(self.content, self._encoding)

    def json(self):
        import ujson
        r = None
        try:
            r= ujson.loads(self.content)
        except Exception as ex:
            _logger.exc(ex, "Failed to read and convert content")
            try:
                if self.content is None:
                    _logger.debug("Content: None")
                else:
                    _logger.debug("Content: {c}".format(c=self.content[0:min(8000,len(self.content))]))
            except:
                pass
        return r


class HttpClient:

    def __init__(self, headers={}):
        self._headers = headers

    def request(self, method, url, data=None, json=None, file=None, custom=None, saveToFile=None, headers={}, stream=None):
        def _write_headers(sock, _headers):
            for k,v in _headers.items():
                sock.write(k.encode())
                sock.write(b": ")
                sock.write(v.encode())
                sock.write(b"\r\n")

        h = dict(self._headers)
        for k,v in headers.items():
            h[k]=v

        _logger.debug("Request: method {method}, url {url}, data {data}, json {json}, file {file}, custom {custom}, saveToFile {saveToFile}, headers={headers}".format(
                method=method, url=url, data=data, json=json, file=file, custom=custom, saveToFile=saveToFile, headers=h))

        try:
            proto, dummy, host, path = url.split('/', 3)
        except ValueError:
            proto, dummy, host = url.split('/', 2)
            path = ''
        if proto == 'http:':
            port = 80
        elif proto == 'https:':
            import ussl
            port = 443
        else:
            raise ValueError('Unsupported protocol: ' + proto)

        if ':' in host:
            host, port = host.split(':', 1)
            port = int(port)

        ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
        if len(ai) < 1:
            raise ValueError('You are not connected to the internet...')
        ai = ai[0]

        s = usocket.socket(ai[0], ai[1], ai[2])
        try:
            s.connect(ai[-1])
            if proto == 'https:':
                s = ussl.wrap_socket(s, server_hostname=host)
            s.write(b'%s /%s HTTP/1.0\r\n' % (method.encode(), path.encode()))
            if not 'Host' in headers:
                s.write(b'Host: %s\r\n' % host.encode())
            # Iterate over keys to avoid tuple alloc
            _write_headers(s, self._headers)
            _write_headers(s, headers)

            # add user agent
            s.write(b'User-Agent: MicroPython Client\r\n')
            if json is not None:
                assert data is None
                import ujson
                data = ujson.dumps(json)
                s.write(b'Content-Type: application/json\r\n')

            if data:
                s.write(b'Content-Length: %d\r\n' % len(data))
                s.write(b'\r\n')
                s.write(data)
            elif file:
                s.write(b'Content-Length: %d\r\n' % os.stat(file)[6])
                s.write(b'\r\n')
                with open(file, 'r') as file_object:
                    for line in file_object:
                        s.write(line + '\n')
            elif custom:
                custom(s)
            else:
                s.write(b'\r\n')

            l = s.readline()
            # print(l)
            l = l.split(None, 2)
            status = int(l[1])
            reason = ''
            if len(l) > 2:
                reason = l[2].rstrip()
            start_ms = utime.ticks_ms()
            while True:
                l = s.readline()
                now_ms = utime.ticks_ms()
                elapsed_ms = utime.ticks_diff(now_ms, start_ms)
                if elapsed_ms > 4000:
                    if WDT_ENABLED:
                        _wdt.feed()
                    utime.sleep_ms(100)
                    start_ms = now_ms
                if not l or l == b'\r\n':
                    break
                # print(l)
                if l.startswith(b'Transfer-Encoding:'):
                    if b'chunked' in l:
                        raise ValueError('Unsupported ' + l)
                elif l.startswith(b'Location:') and not 200 <= status <= 299:
                    raise NotImplementedError('Redirects not yet supported')
        except OSError as ex:
            _logger.exc(ex, "Request failed: method {method}, url {url}, data {data}, json {json}, file {file}, custom {custom}, saveToFile {saveToFile}, headers={headers}".format(
                method=method, url=url, data=data, json=json, file=file, custom=custom, saveToFile=saveToFile, headers=headers))
            s.close()
            raise

        resp = Response(socket=s, saveToFile=saveToFile)
        resp.status_code = status
        resp.reason = reason
        return resp

    def head(self, url, **kw):
        return self.request('HEAD', url, **kw)

    def get(self, url, **kw):
        return self.request('GET', url, **kw)

    def post(self, url, **kw):
        return self.request('POST', url, **kw)

    def put(self, url, **kw):
        return self.request('PUT', url, **kw)

    def patch(self, url, **kw):
        return self.request('PATCH', url, **kw)

    def delete(self, url, **kw):
        return self.request('DELETE', url, **kw)

