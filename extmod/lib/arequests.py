# File copied from urequests.py from micropython-esp32 tree.

import uasyncio as asyncio

try:
    from typing import IO, Any, Dict, Optional
except ImportError:
    pass

import uasyncio
from uasyncio.stream import Stream
from uasyncio import core
from uerrno import EINPROGRESS
import usocket as socket
import ussl

full_debug = False

# async
def open_connection(host, port):
    
    ai = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]  # TODO this is blocking!
    s = socket.socket(ai[0], socket.SOCK_STREAM, ai[2])
    #s.setblocking(False)

    
    ai_aux = ai[-1]
    try:
        s.connect(ai_aux)
        if full_debug: print("Socket connected to {host}:{port}".format(host=host, port=port))
    except OSError as er:
        if full_debug: print("Failed to connect socket to {host}:{port} ({ai_aux})".format(host=host, port=port, ai_aux=ai_aux))
        if er.args[0] != EINPROGRESS:
            raise er
    
    if full_debug: print("Yield core._io_queue.queue_write")
    yield core._io_queue.queue_write(s)
    
            
    if full_debug: print("Wrap raw socket in SSL socket")
    ssls = ussl.wrap_socket(s, server_hostname=host)  # Wrap raw socket in SSL socket
    if full_debug: print("Create uasyncio stream with the SSL socket")
    ss = uasyncio.stream.Stream(ssls)
    
    if full_debug: print("Return SecureSocket")
    return ss, ss


class Response:

    def __init__(self, f: asyncio.StreamReader, status: int, reason: str) -> None:
        self.raw = f
        self.encoding = "utf-8"
        self._cached = None  # type: Optional[bytes]
        self.status_code = status
        self.reason = reason

    async def aclose(self) -> None:
        if self.raw:
            await self.raw.aclose()
            self.raw = None
        self._cached = None

    async def content(self) -> bytes:
        if self._cached is None:
            raw_data = await self.raw.read(-1)  # type: bytes
            self._cached = raw_data
            await self.raw.aclose()
            self.raw = None
            return self._cached
        else:
            return self._cached

    async def text(self) -> str:
        return str(await self.content(), self.encoding)

    async def json(self) -> Any:
        import ujson
        return ujson.loads(await self.content())


async def request(
        method: str, url: str,
        data: Optional[bytes] = None, json: Any = None,
        headers: Dict[str, str] = {},
        stream: Optional[IO[bytes]] = None) -> Response:
    
    is_ssl = False
    try:
        proto, dummy, host, path = url.split("/", 3)
    except ValueError:
        proto, dummy, host = url.split("/", 2)
        path = ""
    if proto == "http:":
        port = 80
    elif proto == "https:":
        # import ussl
        port = 443
        is_ssl = True
    else:
        raise ValueError("Unsupported protocol: " + proto)

    if ":" in host:
        host, str_port = host.split(":", 1)
        port = int(str_port)

    try:
        if is_ssl:
            if full_debug: print("Open ssl connection to {host}:{port} ...".format(host=host, port=port))
            reader, writer = await open_connection(host, port)
        else:
            reader, writer = await asyncio.open_connection(host, port)
    except Exception as ex:
        print("request error in open_connection: {e}".format(e=str(ex)))
        reader, writer = await asyncio.open_connection(host, port)
        
    await writer.awrite(b"%s /%s HTTP/1.0\r\n" % (method.encode(), path.encode()))
    if "Host" not in headers:
        await writer.awrite(b"Host: %s\r\n" % host.encode())
    # Iterate over keys to avoid tuple alloc
    for k in headers:
        await writer.awrite(k)
        await writer.awrite(b": ")
        await writer.awrite(headers[k])
        await writer.awrite(b"\r\n")
    if json is not None:
        assert data is None
        import ujson
        data = ujson.dumps(json).encode('UTF8')
    if data:
        await writer.awrite(b"Content-Length: %d\r\n" % len(data))
    await writer.awrite(b"\r\n")
    if data:
        await writer.awrite(data)

    line = await reader.readline()
    protover, status, msg = line.split(None, 2)
    status = int(status)
    # print(protover, status, msg)
    while True:
        line = await reader.readline()
        if not line or line == b"\r\n":
            break
        # print(line)
        if line.startswith(b"Transfer-Encoding:"):
            if b"chunked" in line:
                raise ValueError("Unsupported " + line)
        elif line.startswith(b"Location:") and not 200 <= status <= 299:
            raise NotImplementedError("Redirects not yet supported")

    resp = Response(reader, status, msg.rstrip())
    return resp


async def head(url: str, **kw: Any) -> Response:
    return await request("HEAD", url, **kw)


async def get(url: str, **kw: Any) -> Response:
    return await request("GET", url, **kw)


async def post(url: str, **kw: Any) -> Response:
    return await request("POST", url, **kw)


async def put(url: str, **kw: Any) -> Response:
    return await request("PUT", url, **kw)


async def patch(url: str, **kw: Any) -> Response:
    return await request("PATCH", url, **kw)


async def delete(url: str, **kw: Any) -> Response:
    return await request("DELETE", url, **kw)
