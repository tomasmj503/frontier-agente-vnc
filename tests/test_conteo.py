"""Regla anti falso éxito: un conteo no se da por bueno con paginación sin recorrer o contra un total."""
import numpy as np

from app.llm import Decision
from app.screen import Elemento, Vista
from app.supervisor import Supervisor

TAREA = "¿Cuántas facturas vencidas tiene Ferretería Ruiz?"


def vista(*textos):
    els = [Elemento(n=i + 1, texto=t, x=10, y=10 * (i + 1), w=50, h=12) for i, t in enumerate(textos)]
    return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)


def cierre(resumen, estado="terminada"):
    return Decision(razon="r", accion="terminar", estado=estado, resumen=resumen)


def test_conteo_con_paginacion_sin_recorrer_se_rechaza():
    sup = Supervisor(tarea=TAREA, secretos=[])
    v = sup.revisar(cierre("Hay 16.\nrespuesta: 16"), vista("Facturas", "Anterior", "Página 1", "Siguiente"))
    assert v.ok is False and "paginación" in v.aviso


def test_tras_dos_avisos_se_convierte_en_fallida_sin_linea_respuesta():
    sup = Supervisor(tarea=TAREA, secretos=[])
    pantalla = vista("Página 1", "Siguiente")
    for _ in range(2):
        assert sup.revisar(cierre("respuesta: 16"), pantalla).ok is False
    v = sup.revisar(cierre("respuesta: 16"), pantalla)
    assert v.ok and v.decision.estado == "fallida"
    assert "respuesta" not in v.decision.resumen.lower().replace("la respuesta dada", "")
    assert "No pude confirmar" in v.decision.resumen


def test_con_varias_paginas_vistas_se_acepta():
    sup = Supervisor(tarea=TAREA, secretos=[])
    sup.revisar(Decision(razon="r", accion="tecla", tecla="tab"), vista("Página 1", "Siguiente"))
    sup.revisar(Decision(razon="r", accion="tecla", tecla="tab"), vista("Página 2", "Siguiente"))
    v = sup.revisar(cierre("respuesta: 45"), vista("Página 3", "Anterior"))
    assert v.ok is True and v.decision is None


def test_pagina_x_de_n_exige_ver_todas():
    sup = Supervisor(tarea=TAREA, secretos=[])
    sup.revisar(Decision(razon="r", accion="tecla", tecla="tab"), vista("Página 1 de 3"))
    v = sup.revisar(cierre("respuesta: 40"), vista("Página 2 de 3"))
    assert v.ok is False
    v = sup.revisar(cierre("respuesta: 45"), vista("Página 3 de 3"))
    assert v.ok is True


def test_total_del_programa_manda_sobre_el_conteo_a_ojo():
    sup = Supervisor(tarea=TAREA, secretos=[])
    pantalla = vista("Facturas", "45 registros")
    assert sup.revisar(cierre("respuesta: 16"), pantalla).ok is False
    assert sup.revisar(cierre("respuesta: 45"), pantalla).ok is True


def test_una_sola_pagina_confirmada_en_el_resumen_se_acepta():
    sup = Supervisor(tarea=TAREA, secretos=[])
    v = sup.revisar(cierre("Es una única página.\nrespuesta: 3"), vista("Página 1", "Siguiente"))
    assert v.ok is True


def test_preguntas_que_no_son_de_conteo_no_se_ven_afectadas():
    sup = Supervisor(tarea="¿Cuál es el teléfono de Ana Torres?", secretos=[])
    v = sup.revisar(cierre("respuesta: 3014445566"), vista("Página 1", "Siguiente"))
    assert v.ok is True
