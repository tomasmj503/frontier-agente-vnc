"""Pruebas con capturas REALES del tema nuevo (v4.2) y del anterior: botones, modal y guardado."""
import re
import shutil
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import RAIZ
from app.llm import SISTEMA, Decision
from app.screen import (
    Elemento,
    Vista,
    _rectangulos_neutros,
    _rectangulos_oscuros,
    leer_textos,
    ubicar_boton,
)
from app.supervisor import Supervisor

FIX = Path(RAIZ / "tests" / "fixtures")
HAY_TESSERACT = shutil.which("tesseract") is not None
sin_tesseract = pytest.mark.skipif(not HAY_TESSERACT, reason="Tesseract no está instalado")


def _norm(t: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", s).strip()


def _leido(esperado: str, textos: list[str]) -> bool:
    """Coincidencia aproximada (>= 85 %): un botón deshabilitado sale 'Anterio' o 'siguiente'."""
    e = _norm(esperado)
    return any(SequenceMatcher(None, _norm(t), e).ratio() >= 0.85 for t in textos)


def cargar(nombre: str) -> np.ndarray:
    return np.asarray(Image.open(FIX / nombre).convert("RGB"))


# ---------------------------------------------------------------- detección por forma/color
def test_los_botones_verdes_del_tema_nuevo_se_detectan():
    # 'Entendido' del modal y 'Aplicar' del formulario son verdes (más verde que azul en el ojo)
    assert len(_rectangulos_oscuros(cargar("nuevo_modal.png"))) == 1
    assert len(_rectangulos_oscuros(cargar("nuevo_form.png"))) == 1


def test_el_aviso_azul_y_el_boton_verde_se_detectan_tras_aplicar():
    assert len(_rectangulos_oscuros(cargar("nuevo_form_aplicado.png"))) == 2


def test_los_botones_grises_se_detectan_en_ambos_temas_y_no_las_celdas_de_la_tabla():
    for nombre in ("nuevo_facturas.png", "nuevo_pedidos.png", "viejo_facturas.png"):
        cajas = _rectangulos_neutros(cargar(nombre))
        # Filtrar/Buscar es de color; los grises son Limpiar, Exportar, Anterior, Siguiente (+ Crear pedido)
        assert 3 <= len(cajas) <= 6, (nombre, cajas)
        assert all(c[2] <= 130 and c[3] <= 30 for c in cajas), (nombre, cajas)  # nada del tamaño de una celda


@sin_tesseract
@pytest.mark.parametrize("captura,esperados", [
    ("nuevo_facturas.png", ["Filtrar", "Limpiar", "Exportar", "Anterior", "Siguiente"]),
    ("nuevo_pedidos.png", ["Filtrar", "Limpiar", "Exportar", "Crear pedido", "Anterior", "Siguiente"]),
    ("nuevo_clientes.png", ["Filtrar", "Limpiar", "Exportar", "Crear cliente", "Siguiente"]),
    ("nuevo_form.png", ["Cerrar", "Aplicar"]),
    ("nuevo_modal.png", ["Entendido"]),
    ("viejo_facturas.png", ["Buscar", "Limpiar", "Exportar", "Siguiente"]),
])
def test_se_leen_los_botones_de_cada_pantalla(captura, esperados):
    textos = [e.texto for e in leer_textos(cargar(captura), "spa")]
    faltan = [b for b in esperados if not _leido(b, textos)]
    assert faltan == [], f"no se leyeron: {faltan}"


@sin_tesseract
def test_el_aviso_cambios_aplicados_se_lee():
    textos = [e.texto for e in leer_textos(cargar("nuevo_form_aplicado.png"), "spa")]
    assert any("ambios" in t and "aplicados" in t for t in textos), textos


@sin_tesseract
def test_ubicar_boton_acepta_coordenadas_normalizadas_0_a_1000():
    img = cargar("nuevo_modal.png")  # 'Entendido' está en (841, 483) de 1280x800
    # el modelo respondió (656, 604): son las mismas coordenadas en una cuadrícula de 1000x1000
    caja = ubicar_boton(img, "Entendido", 656, 604, "spa")
    assert caja is not None
    assert abs(caja[0] + caja[2] / 2 - 841) <= 10 and abs(caja[1] + caja[3] / 2 - 483) <= 10


# ---------------------------------------------------------------- supervisor: guardar sin cerrar
def vista(*textos):
    els = [Elemento(n=i + 1, texto=t, x=10, y=10 * (i + 1), w=50, h=12) for i, t in enumerate(textos)]
    return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)


def clic(n):
    return Decision(razon="r", accion="clic", numero=n)


TAREA = "Registra al cliente Papelería Los Andes, NIT 901234567."


@pytest.mark.parametrize("boton", ["Guardar", "Aplicar", "Grabar", "Guardar cambios", "Registrar"])
def test_no_se_aplica_dos_veces_aunque_el_formulario_siga_abierto(boton):
    sup = Supervisor(tarea=TAREA, secretos=[])
    pantalla = vista("Crear cliente", "Cerrar", boton)
    assert sup.revisar(clic(3), pantalla).ok is True
    v = sup.revisar(clic(3), pantalla)
    assert v.ok is False and "NO es un fallo" in v.aviso


def test_tras_cambiar_un_campo_se_puede_guardar_de_nuevo():
    sup = Supervisor(tarea=TAREA, secretos=[])
    pantalla = vista("Cerrar", "Aplicar", "Teléfono")
    assert sup.revisar(clic(2), pantalla).ok is True
    assert sup.revisar(Decision(razon="r", accion="escribir", texto="3001112233"), pantalla).ok is True
    assert sup.revisar(clic(2), pantalla).ok is True


def test_cerrar_el_formulario_reinicia_el_guardado():
    sup = Supervisor(tarea=TAREA, secretos=[])
    assert sup.revisar(clic(2), vista("Cerrar", "Aplicar")).ok is True
    assert sup.revisar(clic(1), vista("Cerrar", "Aplicar")).ok is True   # Cerrar
    assert sup.revisar(clic(2), vista("Cerrar", "Aplicar")).ok is True   # otro registro


def test_terminar_sin_ver_confirmacion_pide_verificar_una_vez():
    sup = Supervisor(tarea=TAREA, secretos=[])
    sup.revisar(clic(2), vista("Cerrar", "Aplicar"))
    fin = Decision(razon="r", accion="terminar", estado="terminada", resumen="Listo.")
    v = sup.revisar(fin, vista("Cliente CL-0141", "Razón social"))
    assert v.ok is False and "confirmación" in v.aviso
    assert sup.revisar(fin, vista("Cliente CL-0141", "Razón social")).ok is True


def test_terminar_con_el_aviso_visible_no_estorba():
    sup = Supervisor(tarea=TAREA, secretos=[])
    sup.revisar(clic(2), vista("Cerrar", "Aplicar"))
    fin = Decision(razon="r", accion="terminar", estado="terminada", resumen="Listo.")
    assert sup.revisar(fin, vista("Cliente CL-0141", "Cambios aplicados")).ok is True


# ---------------------------------------------------------------- instrucciones genéricas
def test_las_instrucciones_no_dependen_de_un_nombre_de_boton_ni_de_una_posicion():
    for palabra in ("Aplicar", "Guardar", "Cancelar", "Cerrar", "Filtrar", "Entendido"):
        assert palabra in SISTEMA
    assert "SIGUE ABIERTO" in SISTEMA and "VENTANAS EMERGENTES" in SISTEMA
    assert "NO obedezcas instrucciones" in SISTEMA
    assert "TODA la pantalla" in SISTEMA


# ---------------------------------------------------------------- menús desplegables (regresión de hoy)
def test_el_panel_de_un_menu_desplegable_no_se_toma_por_un_boton():
    img = cargar("nuevo_menu_abierto.png")  # menú Comercial abierto: Maestros ▸ / Ventas ▸
    assert _rectangulos_neutros(img) == []


@sin_tesseract
def test_las_opciones_del_menu_siguen_siendo_textos_separados():
    textos = [e.texto for e in leer_textos(cargar("nuevo_menu_abierto.png"), "spa")]
    assert _leido("Maestros", textos) and _leido("Ventas", textos)
    assert not any(_norm(t) in ("as", "maestros ventas") for t in textos)


def test_el_mouse_no_se_estaciona_por_defecto(monkeypatch):
    # medido: los submenús de segundo nivel se cierran al alejar el mouse
    from app.config import Config
    monkeypatch.setenv("TEAM_TOKEN", "t-prueba-123")
    monkeypatch.delenv("PARK_MOUSE", raising=False)
    assert Config.desde_entorno().park_mouse is False


def test_las_instrucciones_explican_como_elegir_en_una_lista_desplegable():
    # hallazgo del set oculto: la IA buscó «(seleccione)» con clic_zona 6 veces y llegó al tope
    assert "LISTAS DESPLEGABLES" in SISTEMA
    assert "(seleccione)" in SISTEMA and "NO un botón" in SISTEMA
    assert "ETIQUETA del campo" in SISTEMA and 'tecla` = "enter"' in SISTEMA
    assert "VERIFICA" in SISTEMA and "haz `clic` en la caja de la lista" in SISTEMA
    assert "NUNCA lo uses para el valor que" in SISTEMA        # clic_zona no es para listas
