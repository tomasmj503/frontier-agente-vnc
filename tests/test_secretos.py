"""Pruebas del filtro de secretos y de que nada sensible sale hacia la IA, el resumen o la bitácora."""
import json
import re
from pathlib import Path

import numpy as np

from app.bitacora import Bitacora
from app.config import RAIZ, Config
from app.llm import Decision, Llm
from app.screen import Elemento, Vista
from app.secretos import OCULTO, contiene_secreto, ocultar
from app.supervisor import Supervisor
from app.vnc import _des_bloque

CLAVE = "clave-super-secreta"


def test_ocultar_reemplaza_todas_las_apariciones():
    assert ocultar(f"a {CLAVE} b {CLAVE}", [CLAVE]) == f"a {OCULTO} b {OCULTO}"


def test_ocultar_primero_los_secretos_mas_largos():
    assert ocultar("abc-def", ["abc", "abc-def"]) == OCULTO


def test_ocultar_ignora_secretos_vacios_o_demasiado_cortos():
    assert ocultar("hola 12 mundo", ["", "12"]) == "hola 12 mundo"


def test_contiene_secreto():
    assert contiene_secreto(f"x{CLAVE}y", [CLAVE])
    assert not contiene_secreto("nada", [CLAVE, ""])


def test_el_mensaje_a_la_ia_no_lleva_la_clave(monkeypatch):
    monkeypatch.setenv("TEAM_TOKEN", "t-prueba-123")
    llm = Llm(Config.desde_entorno(), secretos=[CLAVE], cliente=object())
    msg = llm.mensaje_paso(
        f"Haz algo con {CLAVE}", [f"1. escribir «{CLAVE}»"], f"1 | x=1 y=1 | {CLAVE}", [f"aviso {CLAVE}"]
    )
    assert CLAVE not in msg and OCULTO in msg


def _vista(textos):
    els = [Elemento(n=i + 1, texto=t, x=10, y=10 * (i + 1), w=50, h=10) for i, t in enumerate(textos)]
    return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)


def test_el_supervisor_no_deja_escribir_la_clave():
    sup = Supervisor(tarea="x", secretos=[CLAVE])
    d = Decision(razon="r", accion="escribir", texto=CLAVE)
    assert sup.revisar(d, _vista(["Nombre"])).ok is False


def test_el_supervisor_rechaza_numeros_inexistentes_y_teclas_bloqueadas():
    sup = Supervisor(tarea="x", secretos=[])
    v = _vista(["Archivo", "Clientes"])
    assert sup.revisar(Decision(razon="r", accion="clic", numero=99), v).ok is False
    assert sup.revisar(Decision(razon="r", accion="clic", numero=2), v).ok is True
    for tecla in ("ctrl+l", "F12", "esc"):
        assert sup.revisar(Decision(razon="r", accion="tecla", tecla=tecla), v).ok is False


def test_tarea_fallida_no_lleva_linea_respuesta():
    sup = Supervisor(tarea="¿Cuántas facturas hay?", secretos=[])
    d = Decision(razon="r", accion="terminar", estado="fallida", resumen="No se puede.\nrespuesta: 7")
    ver = sup.revisar(d, _vista(["Inicio"]))
    assert ver.ok and "respuesta" not in ver.decision.resumen.lower()


def test_pregunta_terminada_sin_respuesta_se_pide_corregir_una_vez():
    sup = Supervisor(tarea="¿Cuántas facturas vencidas tiene X?", secretos=[])
    d = Decision(razon="r", accion="terminar", estado="terminada", resumen="Hay 45.")
    assert sup.revisar(d, _vista(["Total"])).ok is False
    assert sup.revisar(d, _vista(["Total"])).ok is True  # segunda vez: no insiste


def test_la_bitacora_no_escribe_secretos(tmp_path):
    b = Bitacora(tmp_path / "t1", [CLAVE])
    b.paso(1, None, {"decision": f"escribí {CLAVE}", "textos": CLAVE})
    b.cierre({"resumen": f"clave {CLAVE}"})
    for f in (tmp_path / "t1").glob("*.json"):
        assert CLAVE not in f.read_text()
    paso = json.loads((tmp_path / "t1" / "paso_01.json").read_text())
    assert paso["decision"] == f"escribí {OCULTO}"


def test_des_vector_clasico():
    # vector clásico de DES: clave 133457799BBCDFF1, texto 0123456789ABCDEF -> 85E813540F0AB405
    got = _des_bloque(bytes.fromhex("133457799BBCDFF1"), bytes.fromhex("0123456789ABCDEF"))
    assert got == bytes.fromhex("85E813540F0AB405")


def test_ningun_archivo_de_codigo_nombra_la_app_de_practica():
    palabra = re.compile("sige" + "com", re.I)
    archivos = [*Path(RAIZ / "app").rglob("*.py"), RAIZ / "bench.py", *Path(RAIZ / "tests").rglob("*.py")]
    malos = [str(a.relative_to(RAIZ)) for a in archivos if palabra.search(a.read_text())]
    assert malos == []


def test_una_razon_muy_larga_se_recorta_en_vez_de_rechazarse():
    d = Decision.model_validate({"razon": "x" * 900, "accion": "tecla", "tecla": "tab"})
    assert len(d.razon) == 300 and d.accion == "tecla"
