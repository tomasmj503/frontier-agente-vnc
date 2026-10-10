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


def test_unica_pagina_sin_probar_siguiente_se_rechaza():
    sup = Supervisor(tarea=TAREA, secretos=[])
    v = sup.revisar(cierre("Es una única página.\nrespuesta: 3"), vista("Página 1", "Siguiente"))
    assert v.ok is False and "Siguiente" in v.aviso and "no lo probaste" in v.aviso


def _clic_siguiente(sup, pantalla):
    n = next(e.n for e in pantalla.elementos if "Siguiente" in e.texto)
    assert sup.revisar(Decision(razon="r", accion="clic", numero=n), pantalla).ok


def test_unica_pagina_con_siguiente_probado_y_sin_cambio_se_acepta():
    sup = Supervisor(tarea=TAREA, secretos=[])
    p1 = vista("Facturas", "Página 1", "Siguiente", "FV-1001", "FV-1002", "FV-1003")
    _clic_siguiente(sup, p1)
    sup.registrar_resultado(True)
    # la pantalla de después es la misma: Siguiente estaba deshabilitado
    v = sup.revisar(cierre("Es una única página.\nrespuesta: 3"), p1)
    assert v.ok is True and v.decision is None


def test_siguiente_que_si_cambia_la_pagina_obliga_a_seguir_recorriendo():
    sup = Supervisor(tarea=TAREA, secretos=[])
    p1 = vista("Facturas", "Página 1", "Siguiente", "FV-1001", "FV-1002", "FV-1003")
    p2 = vista("Facturas", "Página 2", "Siguiente", "FV-2001", "FV-2002", "FV-2003")
    _clic_siguiente(sup, p1)
    sup.registrar_resultado(True)
    sup.revisar(cierre("Es una única página.\nrespuesta: 3"), p2)
    assert sup._unica_comprobada is False   # la página cambió: la afirmación "única página" no se comprobó


def test_unica_pagina_sin_boton_siguiente_visible_se_acepta():
    sup = Supervisor(tarea=TAREA, secretos=[])
    v = sup.revisar(cierre("Es una única página.\nrespuesta: 3"), vista("Facturas", "Página 1", "FV-1001"))
    assert v.ok is True


def test_afirmar_unica_pagina_sin_probar_termina_en_fallida_tras_los_avisos():
    sup = Supervisor(tarea=TAREA, secretos=[])
    pantalla = vista("Página 1", "Siguiente")
    fin = cierre("Es una única página.\nrespuesta: 16")
    assert sup.revisar(fin, pantalla).ok is False
    assert sup.revisar(fin, pantalla).ok is False
    v = sup.revisar(fin, pantalla)
    assert v.ok and v.decision.estado == "fallida"


def test_preguntas_que_no_son_de_conteo_no_se_ven_afectadas():
    sup = Supervisor(tarea="¿Cuál es el teléfono de Ana Torres?", secretos=[])
    v = sup.revisar(cierre("respuesta: 3014445566"), vista("Página 1", "Siguiente"))
    assert v.ok is True
