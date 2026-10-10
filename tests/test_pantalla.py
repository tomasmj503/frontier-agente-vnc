"""Pruebas de la lectura de pantalla: separación de botones pegados y botones azules."""
import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import RAIZ
from app.screen import _agrupar, _limpiar_boton, _rectangulos_oscuros, leer_textos


def _datos(palabras):
    """palabras: lista de (texto, x, ancho). Una sola línea, altura 20, confianza 90."""
    n = len(palabras)
    return {
        "text": [p[0] for p in palabras], "conf": ["90"] * n,
        "block_num": [1] * n, "par_num": [1] * n, "line_num": [1] * n,
        "left": [p[1] for p in palabras], "top": [100] * n,
        "width": [p[2] for p in palabras], "height": [20] * n,
    }


def test_dos_botones_pegados_no_se_fusionan():
    # "Nuevo pedido" | "Exportar": los separa el borde "||" aunque el hueco sea pequeño
    d = _datos([("Nuevo", 20, 50), ("pedido", 74, 55), ("||", 132, 6), ("Exportar", 142, 70)])
    assert [f[0] for f in _agrupar(d)] == ["Nuevo pedido", "Exportar"]


def test_bordes_pegados_a_la_palabra_se_quitan():
    d = _datos([("[30/09/2026", 20, 90)])
    assert [f[0] for f in _agrupar(d)] == ["30/09/2026"]


def test_palabras_de_una_misma_frase_se_unen():
    d = _datos([("Razón", 20, 50), ("social", 76, 50), ("o", 132, 10), ("nombre", 148, 60)])
    assert [f[0] for f in _agrupar(d)] == ["Razón social o nombre"]


def test_limpiar_boton_quita_signos_sueltos():
    assert _limpiar_boton('” Guardar') == "Guardar"
    assert _limpiar_boton('[Buscar "|') == "Buscar"
    assert _limpiar_boton("|” Guardar |") == "Guardar"


def test_rectangulo_azul_del_tamano_de_un_boton():
    img = np.full((200, 400, 3), 240, dtype=np.uint8)
    img[50:73, 20:100] = (64, 107, 170)     # botón 80x23
    img[0:34, :] = (30, 58, 100)            # cabecera: muy ancha, se descarta
    img[120:135, 20:110] = (64, 107, 170)   # línea resaltada de 15 px: demasiado baja
    assert _rectangulos_oscuros(img) == [(20, 50, 80, 23)]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no está instalado")
def test_se_lee_el_boton_guardar_blanco_sobre_azul():
    # captura real del formulario de práctica (carpeta spike/): Guardar es blanco sobre azul
    ruta = Path(RAIZ / "spike" / "p5_6_nuevo_cliente.png")
    textos = [e.texto for e in leer_textos(np.asarray(Image.open(ruta).convert("RGB")), "spa")]
    assert "Guardar" in textos and "Volver" in textos


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no está instalado")
@pytest.mark.parametrize("texto,centro", [("Guardar", (66, 376)), ("Volver", (145, 376))])
def test_ubicar_boton_en_la_zona_que_indica_la_ia(texto, centro):
    from app.screen import ubicar_texto_en_zona
    img = np.asarray(Image.open(RAIZ / "spike" / "p5_6_nuevo_cliente.png").convert("RGB"))
    # la IA se equivoca por 40 px en x y 20 en y: el código igual encuentra el botón exacto
    caja = ubicar_texto_en_zona(img, texto, centro[0] + 40, centro[1] + 20, "spa")
    assert caja is not None
    assert abs(caja[0] + caja[2] / 2 - centro[0]) <= 8 and abs(caja[1] + caja[3] / 2 - centro[1]) <= 8


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no está instalado")
def test_ubicar_boton_que_no_existe_devuelve_none():
    from app.screen import ubicar_texto_en_zona
    img = np.asarray(Image.open(RAIZ / "spike" / "p5_6_nuevo_cliente.png").convert("RGB"))
    assert ubicar_texto_en_zona(img, "Siguiente", 66, 376, "spa") is None
