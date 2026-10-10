"""Ejecuta una lista de acciones sobre el escritorio por VNC y guarda capturas.

Acciones (separadas por espacio, entre comillas si llevan espacios):
    shot:nombre.png        captura completa -> spike/nombre.png
    click:X,Y              mover y hacer clic de 150 ms
    wait:SEGUNDOS          esperar
    key:ctrl+a             combinación de teclas (ctrl, shift, alt, enter, tab, esc, a-z, 0-9)
    type:texto             escribir texto (soporta tildes y ñ)
    reset                  POST /__reset (al final)

Ejemplo:
    .venv/bin/python spike/vnc_actions.py shot:a.png click:122,48 wait:1 shot:b.png
"""
import asyncio
import struct
import sys
import time

import websockets

from vnc_test import RFB, ROOT, SPIKE, http, http_base, load_env

KEYSYMS = {
    "ctrl": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9, "enter": 0xFF0D, "tab": 0xFF09,
    "esc": 0xFF1B, "backspace": 0xFF08, "delete": 0xFFFF, "f12": 0xFFC9,
}


def keysym(ch):
    if ch in KEYSYMS:
        return KEYSYMS[ch]
    o = ord(ch)
    return o if o < 0x100 else 0x01000000 + o  # Latin-1 usa el mismo número; el resto, Unicode


async def key_event(c, sym, down):
    await c.send(struct.pack(">BBxxI", 4, 1 if down else 0, sym))


async def press(c, syms, hold=0.05):
    for s in syms:
        await key_event(c, s, True)
    await asyncio.sleep(hold)
    for s in reversed(syms):
        await key_event(c, s, False)
    await asyncio.sleep(0.03)


async def run(actions):
    env = load_env(ROOT / ".env")
    url, password, token = env["DESKTOP_URL"], env["DESKTOP_PASSWORD"], env["DESKTOP_TOKEN"]
    async with websockets.connect(url, subprotocols=["binary"], max_size=None,
                                  ping_interval=None, open_timeout=20) as ws:
        c = RFB(ws)
        await c.handshake(password)
        for act in actions:
            name, _, arg = act.partition(":")
            t0 = time.perf_counter()
            if name == "shot":
                await c.request_full()
                c.save(SPIKE / arg)
            elif name == "click":
                x, y = (int(v) for v in arg.split(","))
                await c.pointer(0, x, y)
                await asyncio.sleep(0.1)
                await c.pointer(1, x, y)
                await asyncio.sleep(0.150)
                await c.pointer(0, x, y)
            elif name == "wait":
                await asyncio.sleep(float(arg))
            elif name == "key":
                await press(c, [keysym(p) for p in arg.split("+")])
            elif name == "type":
                for ch in arg:
                    await press(c, [keysym(ch)], hold=0.03)
            elif name == "reset":
                st, body = http("POST", http_base(url) + "/__reset", token=token, timeout=60)
                print(f"  /__reset -> {st} {body}")
            else:
                raise SystemExit(f"acción desconocida: {act}")
            print(f"  {act:<40} {(time.perf_counter() - t0) * 1000:6.0f} ms")


if __name__ == "__main__":
    try:
        asyncio.run(run(sys.argv[1:]))
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
