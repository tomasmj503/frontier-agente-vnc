"""Reconexión del VNC si la conexión se corta a mitad de la tarea (con un servidor RFB de mentira)."""
import asyncio
import dataclasses
import struct

import numpy as np
import pytest
from websockets.asyncio.server import serve

import app.agent as agente
from app.agent import Agente, Progreso
from app.bitacora import Bitacora
from app.config import Config
from app.llm import Decision, RespuestaLlm
from app.screen import Elemento, Vista
from app.vnc import ConexionRestablecida, ErrorVnc, Vnc

ANCHO, ALTO = 64, 40


class ServidorRfb:
    """Habla lo mínimo de RFB. `cortar` = {(conexion, tipo_mensaje): n}: aborta al recibir el n-ésimo."""

    def __init__(self, cortar=None):
        self.cortar = cortar or {}
        self.conexiones = 0
        self.recibidos = []      # (conexion, tipo)

    async def manejar(self, ws):
        idx = self.conexiones
        self.conexiones += 1
        await ws.send(b"RFB 003.008\n")
        await ws.recv()
        await ws.send(bytes([1, 2]))
        await ws.recv()
        await ws.send(bytes(16))
        await ws.recv()
        await ws.send(struct.pack(">I", 0))
        await ws.recv()
        nombre = b"falso"
        await ws.send(struct.pack(">HH", ANCHO, ALTO) + bytes(16) + struct.pack(">I", len(nombre)) + nombre)
        buf = bytearray()
        cuenta: dict[int, int] = {}
        try:
            async for msg in ws:
                buf += msg
                while buf:
                    tipo = buf[0]
                    largo = {0: 20, 3: 10, 4: 8, 5: 6}.get(tipo)
                    if tipo == 2:
                        if len(buf) < 4:
                            break
                        largo = 4 + 4 * struct.unpack(">H", bytes(buf[2:4]))[0]
                    if largo is None or len(buf) < largo:
                        break
                    del buf[:largo]
                    self.recibidos.append((idx, tipo))
                    cuenta[tipo] = cuenta.get(tipo, 0) + 1
                    if self.cortar.get((idx, tipo)) == cuenta[tipo]:
                        ws.transport.abort()   # corte brusco, sin cerrar bien
                        return
                    if tipo == 3:
                        pixeles = bytes([30, 60, 90, 0]) * (ANCHO * ALTO)
                        await ws.send(struct.pack(">BxH", 0, 1)
                                      + struct.pack(">HHHHi", 0, 0, ANCHO, ALTO, 0) + pixeles)
        except Exception:
            return


def correr(cortar, prueba, **cfg_extra):
    async def principal():
        srv = ServidorRfb(cortar)
        async with serve(srv.manejar, "127.0.0.1", 0) as server:
            puerto = server.sockets[0].getsockname()[1]
            cfg = dataclasses.replace(Config.desde_entorno(), vnc_read_timeout_s=3, **cfg_extra)
            v = await Vnc.conectar(f"ws://127.0.0.1:{puerto}", "clave", cfg)
            try:
                return await prueba(v, srv)
            finally:
                try:
                    await v.cerrar()
                except Exception:
                    pass
    return asyncio.run(principal())


@pytest.fixture(autouse=True)
def _entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_TOKEN", "t-prueba-123")
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))


def test_si_se_corta_al_capturar_reconecta_y_devuelve_la_imagen():
    async def prueba(v, srv):
        a = await v.capturar()
        b = await v.capturar()           # aquí el servidor corta la conexión
        return a, b, v.reconexiones, srv.conexiones
    a, b, reconexiones, conexiones = correr({(0, 3): 2}, prueba)
    assert a.shape == (ALTO, ANCHO, 3) and b.shape == (ALTO, ANCHO, 3)
    assert tuple(b[0, 0]) == (90, 60, 30)     # B,G,R,X -> R,G,B
    assert reconexiones == 1 and conexiones == 2


def test_si_se_corta_durante_una_accion_no_se_repite_sola():
    async def prueba(v, srv):
        with pytest.raises(ConexionRestablecida):
            await v.clic(10, 10)         # el servidor corta en el 2.º evento del puntero
        punteros_conexion_1 = sum(1 for c, t in srv.recibidos if c == 1 and t == 5)
        img = await v.capturar()         # la sesión nueva funciona
        return v.reconexiones, srv.conexiones, punteros_conexion_1, img.shape
    reconexiones, conexiones, punteros, forma = correr({(0, 5): 2}, prueba)
    assert reconexiones == 1 and conexiones == 2
    assert punteros == 0                 # la acción interrumpida NO se reenvió a la conexión nueva
    assert forma == (ALTO, ANCHO, 3)


def test_un_segundo_corte_ya_no_se_recupera_y_falla_con_claridad():
    async def prueba(v, srv):
        await v.capturar()               # 1.ª captura de la conexión 0: bien
        await v.capturar()               # 2.ª: se corta -> reconecta y entrega
        with pytest.raises(ErrorVnc) as e:
            await v.capturar()           # 1.ª de la conexión 1: también se corta -> sin reconexiones
        return str(e.value), v.reconexiones
    msg, reconexiones = correr({(0, 3): 2, (1, 3): 2}, prueba)
    assert reconexiones == 1 and "no se pudo recuperar" in msg


# ---------------------------------------------------------------- el agente
class VncCorta:
    """Falla (conexión restablecida) en la acción n-ésima y registra lo que sí ejecutó."""
    ancho, alto = 1280, 800

    def __init__(self, falla_en=2):
        self.acciones, self.intentos, self.falla_en = [], 0, falla_en
        self.reconexiones = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def clic(self, x, y):
        self.intentos += 1
        if self.intentos == self.falla_en:
            self.reconexiones += 1
            raise ConexionRestablecida("corte")
        self.acciones.append(("clic", x, y))

    async def tecla(self, t):
        self.acciones.append(("tecla", t))

    async def escribir(self, texto, reemplazar=True):
        self.acciones.append(("escribir", texto))

    async def scroll(self, *a, **k):
        self.acciones.append(("scroll",))


def _vista(*textos):
    els = [Elemento(n=i + 1, texto=t, x=20, y=20 * (i + 1), w=80, h=14) for i, t in enumerate(textos)]
    return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)


def test_el_agente_mira_de_nuevo_y_no_repite_la_accion_cortada(monkeypatch, tmp_path):
    cfg = Config.desde_entorno()
    vnc = VncCorta(falla_en=2)

    async def conectar(*a, **k):
        return vnc

    miradas = []

    async def mirar(*a, **k):
        miradas.append(1)
        return _vista("Menú", "Clientes", "Facturas")

    monkeypatch.setattr(agente.Vnc, "conectar", staticmethod(conectar))
    monkeypatch.setattr(agente, "mirar", mirar)

    def resp(**c):
        base = {"razon": "r"}
        base.update(c)
        return RespuestaLlm(Decision.model_validate(base), 0.001, True, 10, 5, "falso")

    guion = [resp(accion="clic", numero=1),            # ejecuta bien
             resp(accion="clic", numero=2),            # se corta la conexión en esta
             resp(accion="tecla", tecla="tab"),        # la IA decide de nuevo tras mirar
             resp(accion="terminar", estado="fallida", resumen="x")]
    mensajes = []

    class AgenteGuion(Agente):
        async def decidir(self, llm, mensaje, vista):
            mensajes.append(mensaje)
            return guion.pop(0)

    prog = Progreso()
    res = asyncio.run(AgenteGuion(cfg).ejecutar(
        "tarea", "wss://x/websockify", "clave-123", prog, Bitacora(tmp_path / "b", [])))
    assert res.estado == "fallida"
    assert vnc.acciones == [("clic", 20 + 40, 20 + 7), ("tecla", "tab")]   # el clic cortado NO se repitió
    assert "se cortó la conexión y se restableció" in " ".join(prog.historial)
    assert "NO repitas esa acción a ciegas" in mensajes[2]                   # la IA fue avisada
    assert len(miradas) >= 4                                                 # volvió a mirar tras el corte


def test_si_la_conexion_no_se_recupera_la_tarea_termina_fallida_con_explicacion(monkeypatch, tmp_path):
    cfg = Config.desde_entorno()

    class VncRota(VncCorta):
        async def clic(self, x, y):
            raise ErrorVnc("la conexión se cortó y no se pudo recuperar (ConnectionClosedError)")

    vnc = VncRota()

    async def conectar(*a, **k):
        return vnc

    async def mirar(*a, **k):
        return _vista("Menú", "Clientes")

    monkeypatch.setattr(agente.Vnc, "conectar", staticmethod(conectar))
    monkeypatch.setattr(agente, "mirar", mirar)

    class AgenteGuion(Agente):
        async def decidir(self, llm, mensaje, vista):
            return RespuestaLlm(Decision.model_validate({"razon": "r", "accion": "clic", "numero": 1}),
                                0.0, True, 1, 1, "falso")

    res = asyncio.run(AgenteGuion(cfg).ejecutar(
        "tarea", "wss://x/websockify", "clave-123", Progreso(), Bitacora(tmp_path / "b", [])))
    assert res.estado == "fallida" and "conexión" in res.resumen
