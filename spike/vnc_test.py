"""Spike: ¿podemos operar el escritorio por VNC (RFB sobre websocket) con protocolo escrito a mano?

Uso:
    .venv/bin/python spike/vnc_test.py --no-click            # solo captura1
    .venv/bin/python spike/vnc_test.py --x 640 --y 700       # captura1, clic, captura2
    .venv/bin/python spike/vnc_test.py --x 640 --y 700 --reset

Nunca imprime la contraseña ni el token.
"""
import argparse
import asyncio
import struct
import sys
import time
import urllib.request
import zlib
from pathlib import Path
from urllib.parse import urlparse

import websockets

ROOT = Path(__file__).resolve().parent.parent
SPIKE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- .env
def load_env(path):
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


# ---------------------------------------------------------------- DES (para la autenticación VNC)
_IP = [58,50,42,34,26,18,10,2,60,52,44,36,28,20,12,4,62,54,46,38,30,22,14,6,64,56,48,40,32,24,16,8,
       57,49,41,33,25,17,9,1,59,51,43,35,27,19,11,3,61,53,45,37,29,21,13,5,63,55,47,39,31,23,15,7]
_FP = [40,8,48,16,56,24,64,32,39,7,47,15,55,23,63,31,38,6,46,14,54,22,62,30,37,5,45,13,53,21,61,29,
       36,4,44,12,52,20,60,28,35,3,43,11,51,19,59,27,34,2,42,10,50,18,58,26,33,1,41,9,49,17,57,25]
_E = [32,1,2,3,4,5,4,5,6,7,8,9,8,9,10,11,12,13,12,13,14,15,16,17,
      16,17,18,19,20,21,20,21,22,23,24,25,24,25,26,27,28,29,28,29,30,31,32,1]
_P = [16,7,20,21,29,12,28,17,1,15,23,26,5,18,31,10,2,8,24,14,32,27,3,9,19,13,30,6,22,11,4,25]
_PC1 = [57,49,41,33,25,17,9,1,58,50,42,34,26,18,10,2,59,51,43,35,27,19,11,3,60,52,44,36,
        63,55,47,39,31,23,15,7,62,54,46,38,30,22,14,6,61,53,45,37,29,21,13,5,28,20,12,4]
_PC2 = [14,17,11,24,1,5,3,28,15,6,21,10,23,19,12,4,26,8,16,7,27,20,13,2,
        41,52,31,37,47,55,30,40,51,45,33,48,44,49,39,56,34,53,46,42,50,36,29,32]
_SHIFTS = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]
_S = [
    [14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7, 0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,
     4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0, 15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13],
    [15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10, 3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5,
     0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15, 13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9],
    [10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8, 13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,
     13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7, 1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12],
    [7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15, 13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,
     10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4, 3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14],
    [2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9, 14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,
     4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14, 11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3],
    [12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11, 10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,
     9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6, 4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13],
    [4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1, 13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,
     1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2, 6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12],
    [13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7, 1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,
     7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8, 2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11],
]


def _bits(b):
    return [(byte >> (7 - i)) & 1 for byte in b for i in range(8)]


def _bytes(bits):
    return bytes(sum(bits[i + j] << (7 - j) for j in range(8)) for i in range(0, len(bits), 8))


def _perm(bits, table):
    return [bits[i - 1] for i in table]


def des_encrypt_block(key8, block8):
    cd = _perm(_bits(key8), _PC1)
    c, d = cd[:28], cd[28:]
    subkeys = []
    for s in _SHIFTS:
        c, d = c[s:] + c[:s], d[s:] + d[:s]
        subkeys.append(_perm(c + d, _PC2))
    bits = _perm(_bits(block8), _IP)
    left, right = bits[:32], bits[32:]
    for k in subkeys:
        x = [a ^ b for a, b in zip(_perm(right, _E), k)]
        out = []
        for i in range(8):
            ch = x[6 * i:6 * i + 6]
            row = ch[0] * 2 + ch[5]
            col = (ch[1] << 3) | (ch[2] << 2) | (ch[3] << 1) | ch[4]
            v = _S[i][row * 16 + col]
            out += [(v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1]
        f = _perm(out, _P)
        left, right = right, [a ^ b for a, b in zip(left, f)]
    return _bytes(_perm(right + left, _FP))


def vnc_auth_response(password, challenge):
    # VNC usa DES con cada byte de la clave en bit-reversa, clave de 8 bytes (recortada o rellena con ceros)
    key = password.encode("latin-1")[:8].ljust(8, b"\0")
    key = bytes(int(f"{b:08b}"[::-1], 2) for b in key)
    return des_encrypt_block(key, challenge[:8]) + des_encrypt_block(key, challenge[8:16])


def _selftest_des():
    # vector clásico de DES: clave 133457799BBCDFF1, texto 0123456789ABCDEF -> 85E813540F0AB405
    got = des_encrypt_block(bytes.fromhex("133457799BBCDFF1"), bytes.fromhex("0123456789ABCDEF"))
    assert got == bytes.fromhex("85E813540F0AB405"), "DES mal implementado"


# ---------------------------------------------------------------- PNG sin librerías
def write_png(path, w, h, bgra):
    raw = bytearray()
    for y in range(h):
        row = bgra[y * w * 4:(y + 1) * w * 4]
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        raw.append(0)
        raw += rgb

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    Path(path).write_bytes(png)


# ---------------------------------------------------------------- cliente RFB mínimo
class RFB:
    def __init__(self, ws):
        self.ws = ws
        self.buf = bytearray()
        self.w = self.h = 0
        self.fb = None
        self.name = ""

    async def read(self, n):
        while len(self.buf) < n:
            msg = await self.ws.recv()
            if isinstance(msg, str):
                msg = msg.encode("latin-1")
            self.buf += msg
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    async def send(self, data):
        await self.ws.send(data)

    async def handshake(self, password):
        ver = await self.read(12)
        if not ver.startswith(b"RFB "):
            raise RuntimeError(f"no parece RFB: {ver[:12]!r}")
        await self.send(b"RFB 003.008\n")
        n = (await self.read(1))[0]
        if n == 0:
            ln = struct.unpack(">I", await self.read(4))[0]
            raise RuntimeError("servidor rechazó: " + (await self.read(ln)).decode("latin-1"))
        types = list(await self.read(n))
        if 2 not in types:
            raise RuntimeError(f"el servidor no ofrece autenticación VNC (ofrece {types})")
        await self.send(bytes([2]))
        challenge = await self.read(16)
        await self.send(vnc_auth_response(password, challenge))
        result = struct.unpack(">I", await self.read(4))[0]
        if result != 0:
            reason = ""
            try:
                ln = struct.unpack(">I", await asyncio.wait_for(self.read(4), 2))[0]
                reason = (await self.read(ln)).decode("latin-1")
            except Exception:
                pass
            raise RuntimeError(f"autenticación VNC rechazada ({reason or 'sin motivo'})")
        await self.send(b"\x01")  # ClientInit: escritorio compartido
        self.w, self.h = struct.unpack(">HH", await self.read(4))
        await self.read(16)  # formato de píxel del servidor (lo reemplazamos abajo)
        ln = struct.unpack(">I", await self.read(4))[0]
        self.name = (await self.read(ln)).decode("latin-1")
        self.fb = bytearray(self.w * self.h * 4)
        # SetPixelFormat: 32 bpp, profundidad 24, little-endian, true color, R<<16 G<<8 B -> bytes B,G,R,X
        await self.send(struct.pack(">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
        # SetEncodings: solo Raw (0)
        await self.send(struct.pack(">BxHi", 2, 1, 0))

    async def request_full(self):
        await self.send(struct.pack(">BBHHHH", 3, 0, 0, 0, self.w, self.h))
        await self._read_update()

    async def _read_update(self):
        while True:
            t = (await self.read(1))[0]
            if t == 0:
                await self.read(1)
                nrects = struct.unpack(">H", await self.read(2))[0]
                for _ in range(nrects):
                    x, y, w, h, enc = struct.unpack(">HHHHi", await self.read(12))
                    if enc != 0:
                        raise RuntimeError(f"codificación inesperada {enc}")
                    data = await self.read(w * h * 4)
                    for r in range(h):
                        o = ((y + r) * self.w + x) * 4
                        self.fb[o:o + w * 4] = data[r * w * 4:(r + 1) * w * 4]
                return
            elif t == 1:  # SetColourMapEntries
                await self.read(1)
                _, n = struct.unpack(">HH", await self.read(4))
                await self.read(n * 6)
            elif t == 2:  # Bell
                pass
            elif t == 3:  # ServerCutText
                await self.read(3)
                ln = struct.unpack(">I", await self.read(4))[0]
                await self.read(ln)
            else:
                raise RuntimeError(f"mensaje del servidor desconocido: {t}")

    async def pointer(self, mask, x, y):
        await self.send(struct.pack(">BBHH", 5, mask, x, y))

    def save(self, path):
        write_png(path, self.w, self.h, self.fb)


# ---------------------------------------------------------------- pasos
def http_base(ws_url):
    u = urlparse(ws_url)
    return ("https" if u.scheme == "wss" else "http") + "://" + u.netloc


def http(method, url, token=None, timeout=20):
    req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    req.add_header("User-Agent", "frontier-spike/0.1")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")[:300]


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x", type=int, default=None)
    ap.add_argument("--y", type=int, default=None)
    ap.add_argument("--no-click", action="store_true")
    ap.add_argument("--reset", action="store_true", help="al final llama POST /__reset")
    a = ap.parse_args()

    _selftest_des()
    env = load_env(ROOT / ".env")
    url, password, token = env["DESKTOP_URL"], env["DESKTOP_PASSWORD"], env["DESKTOP_TOKEN"]
    t = {}

    def mark(name, t0):
        t[name] = (time.perf_counter() - t0) * 1000
        print(f"  [{name}] {t[name]:.0f} ms")

    print("== Spike VNC ==  (tiempos MEDIDOS en esta corrida)")
    t0 = time.perf_counter()
    try:
        st, body = http("GET", http_base(url) + "/health")
        print(f"  /health -> {st} {body}")
    except Exception as e:
        print(f"  /health falló: {type(e).__name__}: {e}")
    mark("health", t0)

    t0 = time.perf_counter()
    async with websockets.connect(url, subprotocols=["binary"], max_size=None,
                                  ping_interval=None, open_timeout=20) as ws:
        print(f"  subprotocolo negociado: {ws.subprotocol}")
        mark("conexion_websocket", t0)

        c = RFB(ws)
        t0 = time.perf_counter()
        await c.handshake(password)
        mark("handshake_y_autenticacion", t0)
        print(f"  pantalla: {c.w}x{c.h}  nombre: {c.name!r}")

        t0 = time.perf_counter()
        await c.request_full()
        mark("captura1", t0)
        c.save(SPIKE / "captura1.png")
        print("  guardada spike/captura1.png")

        if not a.no_click and a.x is not None and a.y is not None:
            t0 = time.perf_counter()
            await c.pointer(0, a.x, a.y)
            mark("mover_mouse", t0)

            await asyncio.sleep(0.1)
            t0 = time.perf_counter()
            await c.pointer(1, a.x, a.y)
            await asyncio.sleep(0.150)
            await c.pointer(0, a.x, a.y)
            mark("clic_150ms", t0)

            t0 = time.perf_counter()
            await asyncio.sleep(1.0)
            mark("espera_1s", t0)

            t0 = time.perf_counter()
            await c.request_full()
            mark("captura2", t0)
            c.save(SPIKE / "captura2.png")
            print("  guardada spike/captura2.png")
        else:
            print("  (sin clic: falta --x/--y o se pidió --no-click)")

    if a.reset:
        t0 = time.perf_counter()
        try:
            st, body = http("POST", http_base(url) + "/__reset", token=token, timeout=60)
            print(f"  /__reset -> {st} {body}")
        except Exception as e:
            print(f"  /__reset falló: {type(e).__name__}: {e}")
        mark("reset", t0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
