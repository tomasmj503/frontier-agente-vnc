"""El ciclo del agente con un escritorio y una IA de mentira."""
import asyncio

import numpy as np
import pytest

import app.agent as agente
from app.agent import Agente, Progreso
from app.bitacora import Bitacora
from app.config import Config
from app.llm import Decision, ErrorLlm, RespuestaLlm
from app.screen import Elemento, Vista


class VncFalso:
    ancho, alto = 1280, 800

    def __init__(self):
        self.acciones = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def clic(self, x, y):
        self.acciones.append(("clic", x, y))

    async def escribir(self, texto, reemplazar=True):
        self.acciones.append(("escribir", texto))

    async def tecla(self, t):
        self.acciones.append(("tecla", t))

    async def scroll(self, *a, **k):
        self.acciones.append(("scroll",))


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_TOKEN", "t-prueba-123")
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    vnc = VncFalso()

    async def conectar(*a, **k):
        return vnc

    async def mirar(*a, **k):
        els = [Elemento(n=1, texto="Archivo", x=10, y=10, w=50, h=12)]
        return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)

    monkeypatch.setattr(agente.Vnc, "conectar", staticmethod(conectar))
    monkeypatch.setattr(agente, "mirar", mirar)
    return Config.desde_entorno(), vnc, tmp_path


def _respuesta(**campos):
    base = {"razon": "r", "accion": "tecla", "tecla": "tab"}
    base.update(campos)
    return RespuestaLlm(Decision.model_validate(base), 0.001, True, 10, 5, "modelo-falso")


def _correr(cfg, tmp_path, guion):
    """guion: lista de respuestas o excepciones que la IA de mentira da, en orden."""
    class AgenteGuion(Agente):
        async def decidir(self, llm, mensaje, vista):
            x = guion.pop(0)
            if isinstance(x, Exception):
                raise x
            return x

    ag = AgenteGuion(cfg)
    progreso = Progreso()
    res = asyncio.run(ag.ejecutar("Haz algo", "wss://x/websockify", "clave-123", progreso,
                                  Bitacora(tmp_path / "b", ["clave-123"])))
    return res, progreso


def test_un_formato_invalido_se_reintenta_y_la_tarea_sigue(entorno):
    cfg, vnc, tmp = entorno
    guion = [
        ErrorLlm("formato", 0.002, formato=True),
        _respuesta(accion="clic", numero=1),
        _respuesta(accion="terminar", estado="terminada", resumen="Listo."),
    ]
    res, prog = _correr(cfg, tmp, guion)
    assert res.estado == "terminada" and res.resumen == "Listo."
    assert vnc.acciones and vnc.acciones[0][0] == "clic"
    assert prog.costo_usd == pytest.approx(0.002 + 0.001 + 0.001)


def test_tres_formatos_invalidos_seguidos_dejan_la_tarea_fallida(entorno):
    cfg, vnc, tmp = entorno
    guion = [ErrorLlm("formato", 0.0, formato=True) for _ in range(3)]
    res, _ = _correr(cfg, tmp, guion)
    assert res.estado == "fallida" and "formato" in res.resumen
    assert vnc.acciones == []  # nunca tocó el escritorio


def test_un_error_de_la_ia_que_no_es_de_formato_falla_de_inmediato(entorno):
    cfg, vnc, tmp = entorno
    res, _ = _correr(cfg, tmp, [ErrorLlm("sin red", 0.0, formato=False)])
    assert res.estado == "fallida" and "no pudo decidir" in res.resumen


def test_el_resumen_final_no_lleva_la_clave(entorno):
    cfg, _, tmp = entorno
    guion = [_respuesta(accion="terminar", estado="terminada", resumen="La clave es clave-123.")]
    res, _ = _correr(cfg, tmp, guion)
    assert "clave-123" not in res.resumen


def test_clic_zona_hace_clic_en_el_centro_del_boton_encontrado(entorno, monkeypatch):
    cfg, vnc, tmp = entorno
    monkeypatch.setattr(agente, "ubicar_boton", lambda img, texto, x, y, lang: (100, 200, 80, 24))
    guion = [
        _respuesta(accion="clic_zona", texto="Siguiente", zona_x=210, zona_y=690),
        _respuesta(accion="terminar", estado="terminada", resumen="Listo."),
    ]
    res, _ = _correr(cfg, tmp, guion)
    assert res.estado == "terminada"
    assert vnc.acciones == [("clic", 140, 212)]


def test_clic_zona_sin_boton_no_toca_nada_y_la_ia_corrige(entorno, monkeypatch):
    cfg, vnc, tmp = entorno
    monkeypatch.setattr(agente, "ubicar_boton", lambda img, texto, x, y, lang: None)
    guion = [
        _respuesta(accion="clic_zona", texto="Siguiente", zona_x=210, zona_y=690),
        _respuesta(accion="terminar", estado="fallida", resumen="No pude paginar."),
    ]
    res, _ = _correr(cfg, tmp, guion)
    assert res.estado == "fallida" and vnc.acciones == []


def test_clic_zona_exige_texto_y_coordenadas_dentro_de_la_pantalla():
    with pytest.raises(ValueError):
        Decision.model_validate({"razon": "r", "accion": "clic_zona", "texto": "", "zona_x": 5, "zona_y": 5})
    with pytest.raises(ValueError):
        Decision.model_validate(
            {"razon": "r", "accion": "clic_zona", "texto": "Siguiente", "zona_x": 0, "zona_y": 100})
    with pytest.raises(ValueError):
        Decision.model_validate(
            {"razon": "r", "accion": "clic_zona", "texto": "Siguiente", "zona_x": 2000, "zona_y": 100})


def test_las_notas_de_la_ia_vuelven_en_los_pasos_siguientes(entorno):
    cfg, vnc, tmp = entorno
    vistos = []

    class AgenteCaptura(Agente):
        async def decidir(self, llm, mensaje, vista):
            vistos.append(mensaje)
            return guion.pop(0)

    guion = [
        _respuesta(accion="tecla", tecla="tab",
                   nota="Página 1: 16 exactas de 20 (descarté 4: Ferretería Ruiz e Hijos)"),
        _respuesta(accion="tecla", tecla="tab", nota="Página 2: 15 exactas de 20 (descarté 5)"),
        _respuesta(accion="terminar", estado="fallida", resumen="x"),
    ]
    asyncio.run(AgenteCaptura(cfg).ejecutar(
        "¿Cuántas facturas vencidas tiene Ferretería Ruiz?", "wss://x/websockify", "clave-123",
        Progreso(), Bitacora(tmp / "b", [])))
    assert "TUS NOTAS" not in vistos[0]
    assert "Página 1: 16 exactas" in vistos[1] and "Página 2" not in vistos[1]
    assert "Página 1: 16 exactas" in vistos[2] and "Página 2: 15 exactas" in vistos[2]
