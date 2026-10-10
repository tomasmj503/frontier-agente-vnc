"""Cliente VNC (protocolo RFB sobre websocket), escrito a mano.

Limpio a partir de spike/vnc_test.py y spike/vnc_actions.py. Lo que hace:
  - conectar y autenticar (con 1 reintento si la conexión se cuelga)
  - capturar la pantalla completa
  - clic con duración controlada (la app ignora clics de menos de 100 ms)
  - escribir texto (con Ctrl+A antes, para no concatenar), teclas, scroll
"""
import asyncio
import struct

import numpy as np
import websockets

from app.config import Config

# ------------------------------------------------------------------ DES (autenticación VNC)
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


def _bits(b: bytes) -> list[int]:
    return [(byte >> (7 - i)) & 1 for byte in b for i in range(8)]


def _bytes(bits: list[int]) -> bytes:
    return bytes(sum(bits[i + j] << (7 - j) for j in range(8)) for i in range(0, len(bits), 8))


def _perm(bits: list[int], table: list[int]) -> list[int]:
    return [bits[i - 1] for i in table]


def _des_bloque(clave8: bytes, bloque8: bytes) -> bytes:
    cd = _perm(_bits(clave8), _PC1)
    c, d = cd[:28], cd[28:]
    subclaves = []
    for s in _SHIFTS:
        c, d = c[s:] + c[:s], d[s:] + d[:s]
        subclaves.append(_perm(c + d, _PC2))
    bits = _perm(_bits(bloque8), _IP)
    izq, der = bits[:32], bits[32:]
    for k in subclaves:
        x = [a ^ b for a, b in zip(_perm(der, _E), k, strict=True)]
        salida: list[int] = []
        for i in range(8):
            ch = x[6 * i:6 * i + 6]
            fila = ch[0] * 2 + ch[5]
            col = (ch[1] << 3) | (ch[2] << 2) | (ch[3] << 1) | ch[4]
            v = _S[i][fila * 16 + col]
            salida += [(v >> 3) & 1, (v >> 2) & 1, (v >> 1) & 1, v & 1]
        f = _perm(salida, _P)
        izq, der = der, [a ^ b for a, b in zip(izq, f, strict=True)]
    return _bytes(_perm(der + izq, _FP))


def respuesta_autenticacion(password: str, desafio: bytes) -> bytes:
    """VNC cifra el desafío con DES; cada byte de la clave va en bit-reversa, 8 bytes máximo."""
    clave = password.encode("latin-1")[:8].ljust(8, b"\0")
    clave = bytes(int(f"{b:08b}"[::-1], 2) for b in clave)
    return _des_bloque(clave, desafio[:8]) + _des_bloque(clave, desafio[8:16])


# ------------------------------------------------------------------ teclas
TECLAS = {
    "ctrl": 0xFFE3, "shift": 0xFFE1, "alt": 0xFFE9, "enter": 0xFF0D, "tab": 0xFF09,
    "esc": 0xFF1B, "backspace": 0xFF08, "delete": 0xFFFF, "space": 0x20,
    "up": 0xFF52, "down": 0xFF54, "left": 0xFF51, "right": 0xFF53,
    "home": 0xFF50, "end": 0xFF57, "pageup": 0xFF55, "pagedown": 0xFF56,
}


def keysym(nombre: str) -> int:
    """Número de tecla VNC para un nombre ('enter', 'tab') o un carácter suelto ('a', 'ñ')."""
    clave = nombre.lower() if len(nombre) > 1 else nombre
    if clave in TECLAS:
        return TECLAS[clave]
    if len(nombre) == 1:
        o = ord(nombre)
        return o if o < 0x100 else 0x01000000 + o  # Latin-1 usa el mismo número; el resto, Unicode
    if clave.startswith("f") and clave[1:].isdigit() and 1 <= int(clave[1:]) <= 12:
        return 0xFFBE + int(clave[1:]) - 1
    raise ValueError(f"tecla desconocida: {nombre!r}")


class ErrorVnc(RuntimeError):
    pass


class Vnc:
    """Una sesión VNC. Úsala con `async with Vnc.conectar(url, password, cfg) as v:`."""

    def __init__(self, ws, cfg: Config):
        self._ws = ws
        self._cfg = cfg
        self._buf = bytearray()
        self.ancho = 0
        self.alto = 0
        self._fb = bytearray()

    # ---- conexión
    @classmethod
    async def conectar(cls, url: str, password: str, cfg: Config) -> "Vnc":
        """Conecta y autentica. Reintenta `vnc_connect_retries` veces si la conexión se cuelga."""
        ultimo: Exception | None = None
        for _ in range(cfg.vnc_connect_retries + 1):
            ws = None
            try:
                ws = await websockets.connect(
                    url, subprotocols=["binary"], max_size=None,
                    ping_interval=None, open_timeout=cfg.vnc_open_timeout_s,
                )
                v = cls(ws, cfg)
                await asyncio.wait_for(v._saludo(password), timeout=cfg.vnc_open_timeout_s)
                return v
            except Exception as e:  # red, tiempo agotado, protocolo
                ultimo = e
                if ws is not None:
                    await ws.close()
        raise ErrorVnc(f"no se pudo conectar al escritorio: {type(ultimo).__name__}")

    async def cerrar(self) -> None:
        await self._ws.close()

    async def __aenter__(self) -> "Vnc":
        return self

    async def __aexit__(self, *_) -> None:
        await self.cerrar()

    # ---- bajo nivel
    async def _leer(self, n: int) -> bytes:
        while len(self._buf) < n:
            msg = await self._ws.recv()
            if isinstance(msg, str):
                msg = msg.encode("latin-1")
            self._buf += msg
        salida = bytes(self._buf[:n])
        del self._buf[:n]
        return salida

    async def _enviar(self, datos: bytes) -> None:
        await self._ws.send(datos)

    async def _saludo(self, password: str) -> None:
        version = await self._leer(12)
        if not version.startswith(b"RFB "):
            raise ErrorVnc("el servidor no habla RFB")
        await self._enviar(b"RFB 003.008\n")
        n = (await self._leer(1))[0]
        if n == 0:
            largo = struct.unpack(">I", await self._leer(4))[0]
            raise ErrorVnc("servidor rechazó: " + (await self._leer(largo)).decode("latin-1"))
        tipos = list(await self._leer(n))
        if 2 not in tipos:
            raise ErrorVnc(f"el servidor no ofrece autenticación VNC (ofrece {tipos})")
        await self._enviar(bytes([2]))
        desafio = await self._leer(16)
        await self._enviar(respuesta_autenticacion(password, desafio))
        if struct.unpack(">I", await self._leer(4))[0] != 0:
            raise ErrorVnc("autenticación VNC rechazada")
        await self._enviar(b"\x01")  # ClientInit: escritorio compartido
        self.ancho, self.alto = struct.unpack(">HH", await self._leer(4))
        await self._leer(16)  # formato de píxel del servidor (lo reemplazamos abajo)
        largo = struct.unpack(">I", await self._leer(4))[0]
        await self._leer(largo)  # nombre del escritorio
        self._fb = bytearray(self.ancho * self.alto * 4)
        # SetPixelFormat: 32 bpp, profundidad 24, little-endian, color real -> bytes B,G,R,X
        await self._enviar(struct.pack(">BxxxBBBBHHHBBBxxx", 0, 32, 24, 0, 1, 255, 255, 255, 16, 8, 0))
        # SetEncodings: solo Raw (0)
        await self._enviar(struct.pack(">BxHi", 2, 1, 0))

    async def _leer_actualizacion(self) -> None:
        while True:
            tipo = (await self._leer(1))[0]
            if tipo == 0:  # FramebufferUpdate
                await self._leer(1)
                n = struct.unpack(">H", await self._leer(2))[0]
                for _ in range(n):
                    x, y, w, h, enc = struct.unpack(">HHHHi", await self._leer(12))
                    if enc != 0:
                        raise ErrorVnc(f"codificación inesperada {enc}")
                    datos = await self._leer(w * h * 4)
                    for r in range(h):
                        o = ((y + r) * self.ancho + x) * 4
                        self._fb[o:o + w * 4] = datos[r * w * 4:(r + 1) * w * 4]
                return
            if tipo == 1:  # SetColourMapEntries
                await self._leer(1)
                _, n = struct.unpack(">HH", await self._leer(4))
                await self._leer(n * 6)
            elif tipo == 2:  # Bell
                pass
            elif tipo == 3:  # ServerCutText
                await self._leer(3)
                largo = struct.unpack(">I", await self._leer(4))[0]
                await self._leer(largo)
            else:
                raise ErrorVnc(f"mensaje del servidor desconocido: {tipo}")

    # ---- ver
    async def capturar(self) -> np.ndarray:
        """Captura completa. Devuelve un arreglo alto×ancho×3 (RGB, uint8)."""
        await self._enviar(struct.pack(">BBHHHH", 3, 0, 0, 0, self.ancho, self.alto))
        await self._leer_actualizacion()
        bgra = np.frombuffer(bytes(self._fb), dtype=np.uint8).reshape(self.alto, self.ancho, 4)
        return bgra[:, :, 2::-1].copy()  # B,G,R,X -> R,G,B

    # ---- actuar
    async def _puntero(self, mascara: int, x: int, y: int) -> None:
        await self._enviar(struct.pack(">BBHH", 5, mascara, x, y))

    async def clic(self, x: int, y: int) -> None:
        """Mover, esperar, bajar, mantener `click_hold_ms` y soltar."""
        x = max(0, min(self.ancho - 1, int(x)))
        y = max(0, min(self.alto - 1, int(y)))
        await self._puntero(0, x, y)
        await asyncio.sleep(self._cfg.click_move_ms / 1000)
        await self._puntero(1, x, y)
        try:
            await asyncio.sleep(self._cfg.click_hold_ms / 1000)
        finally:  # aunque la tarea se cancele a medias, el botón se suelta
            await self._puntero(0, x, y)

    async def scroll(self, x: int, y: int, direccion: str, pasos: int = 3) -> None:
        """Rueda del mouse sobre (x, y): botón 4 = arriba, botón 5 = abajo."""
        mascara = 8 if direccion == "arriba" else 16
        await self._puntero(0, x, y)
        for _ in range(pasos):
            await self._puntero(mascara, x, y)
            await asyncio.sleep(0.03)
            await self._puntero(0, x, y)
            await asyncio.sleep(0.05)

    async def _evento_tecla(self, sym: int, abajo: bool) -> None:
        await self._enviar(struct.pack(">BBxxI", 4, 1 if abajo else 0, sym))

    async def _pulsar(self, simbolos: list[int], sostener_ms: float) -> None:
        for s in simbolos:
            await self._evento_tecla(s, True)
        try:
            await asyncio.sleep(sostener_ms / 1000)
        finally:  # las teclas siempre se sueltan
            for s in reversed(simbolos):
                await self._evento_tecla(s, False)
        await asyncio.sleep(0.03)

    async def tecla(self, combinacion: str) -> None:
        """Una tecla o combinación: 'enter', 'tab', 'ctrl+a'."""
        simbolos = [keysym(p) for p in combinacion.split("+")]
        await self._pulsar(simbolos, self._cfg.key_hold_ms)

    async def escribir(self, texto: str, reemplazar: bool = True) -> None:
        """Escribe el texto tal cual (tildes, ñ, # y @). Con `reemplazar`, Ctrl+A antes."""
        if reemplazar:
            await self.tecla("ctrl+a")
        for ch in texto:
            await self._pulsar([keysym(ch)], self._cfg.type_hold_ms)
