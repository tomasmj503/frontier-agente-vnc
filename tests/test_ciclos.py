"""Regla general anti-ciclo: repetir la misma secuencia de acciones sobre la misma pantalla se prohíbe.

El caso real: abrir la cita C-1460 -> Cerrar -> filtrar -> abrir la misma cita otra vez, hasta el tope.
Nada de esto depende de una app: se razona con textos de botones y con la huella de la pantalla.
"""
import asyncio

import numpy as np

import app.agent as agente
from app.agent import Agente, Progreso
from app.bitacora import Bitacora
from app.config import Config
from app.llm import Decision, RespuestaLlm
from app.screen import Elemento, Vista
from app.supervisor import Supervisor

TAREA = "¿Qué motivo tiene la cita C-1460?"


def vista(*textos: str) -> Vista:
    els = [Elemento(n=i + 1, texto=t, x=20, y=20 * (i + 1), w=80, h=14) for i, t in enumerate(textos)]
    return Vista(imagen=np.zeros((8, 8, 3), dtype=np.uint8), elementos=els)


LISTA = vista("Citas", "C-1460", "Filtrar", "C-1461", "C-1462", "Paciente", "Fecha", "Estado")
DETALLE = vista("Cita C-1460", "Observaciones", "Cerrar", "Paciente", "Motivo")


def clic(n: int) -> Decision:
    return Decision(razon="r", accion="clic", numero=n)


def sup() -> Supervisor:
    return Supervisor(tarea=TAREA, secretos=[])


def hacer(s: Supervisor, decision: Decision, pantalla: Vista, cambio: bool = True):
    v = s.revisar(decision, pantalla)
    if v.ok:
        s.registrar_resultado(cambio)
    return v


# ---------------------------------------------------------------- el ciclo de la clínica
def ciclo_hasta_el_cuarto_paso(s: Supervisor) -> None:
    assert hacer(s, clic(2), LISTA).ok          # abre C-1460
    assert hacer(s, clic(3), DETALLE).ok        # Cerrar
    assert hacer(s, clic(3), LISTA).ok          # Filtrar
    assert hacer(s, clic(2), LISTA).ok          # abre C-1460 otra vez


def test_repetir_abrir_cerrar_se_prohibe_y_se_explica():
    s = sup()
    ciclo_hasta_el_cuarto_paso(s)
    v = s.revisar(clic(3), DETALLE)             # Cerrar de nuevo: completa la secuencia repetida
    assert v.ok is False
    assert "PROHIBIDA" in v.aviso and "C-1460" in v.aviso and "Cerrar" in v.aviso
    assert any("C-1460" in x for x in s.prohibidas)


def test_la_prohibicion_se_mantiene_si_la_ia_insiste():
    s = sup()
    ciclo_hasta_el_cuarto_paso(s)
    assert s.revisar(clic(3), DETALLE).ok is False
    assert s.revisar(clic(3), DETALLE).ok is False   # insiste: sigue prohibido


def test_probar_otra_cosa_si_se_permite():
    s = sup()
    ciclo_hasta_el_cuarto_paso(s)
    assert s.revisar(clic(3), DETALLE).ok is False
    otro = Decision(razon="r", accion="scroll", direccion="abajo")
    assert hacer(s, otro, DETALLE).ok is True        # desplazarse
    otro_boton = clic(4)                              # otro enlace de la lista
    assert hacer(s, otro_boton, LISTA).ok is True


def test_funciona_con_otros_nombres_de_botones():
    """Nada fijo a una app: otros textos, la misma estructura."""
    lista = vista("Pacientes", "P-0001", "Buscar", "P-0002", "Nombre", "Edad")
    ficha = vista("Ficha P-0001", "Notas", "Volver", "Edad")
    s = sup()
    assert hacer(s, clic(2), lista).ok and hacer(s, clic(3), ficha).ok
    assert hacer(s, clic(3), lista).ok and hacer(s, clic(2), lista).ok
    assert s.revisar(clic(3), ficha).ok is False


# ---------------------------------------------------------------- lo que NO debe bloquearse
def test_dos_registros_distintos_con_los_mismos_botones_no_son_un_ciclo():
    s = sup()
    lista = vista("Clientes", "CL-0007", "CL-0009", "Filtrar", "Nombre", "NIT", "Ciudad")
    form_a = vista("Cliente CL-0007", "Distribuciones El Faro", "900456123", "Bogotá", "Aplicar", "Cerrar")
    form_b = vista("Cliente CL-0009", "Comercial Gómez", "800111222", "Cali", "Aplicar", "Cerrar")
    assert hacer(s, clic(2), lista).ok
    assert hacer(s, Decision(razon="r", accion="escribir", texto="Calle 1"), form_a).ok
    assert hacer(s, clic(5), form_a).ok          # Aplicar
    assert hacer(s, clic(6), form_a).ok          # Cerrar
    assert hacer(s, clic(3), lista).ok           # abre OTRO registro
    assert hacer(s, Decision(razon="r", accion="escribir", texto="Calle 1"), form_b).ok
    assert hacer(s, clic(5), form_b).ok          # Aplicar (otro registro, otra pantalla)
    assert hacer(s, clic(6), form_b).ok


def test_paginar_con_siguiente_no_es_un_ciclo():
    s = sup()
    for pagina in (1, 2, 3, 4):
        p = vista("Facturas", f"Página {pagina}", "Siguiente", "Anterior",
                  f"FV-{pagina}001", f"FV-{pagina}002")
        assert hacer(s, clic(3), p).ok


def test_volver_a_contar_una_pagina_y_seguir_no_se_bloquea():
    s = sup()
    p1 = vista("Facturas", "Página 1", "Siguiente", "Anterior", "FV-1001", "FV-1002", "FV-1003")
    p2 = vista("Facturas", "Página 2", "Siguiente", "Anterior", "FV-2001", "FV-2002", "FV-2003")
    assert hacer(s, clic(3), p1).ok      # Siguiente
    assert hacer(s, clic(4), p2).ok      # Anterior (recontar)
    assert hacer(s, clic(3), p1).ok      # Siguiente otra vez
    assert hacer(s, clic(3), p2).ok      # Siguiente: avanza a la 3


def test_reintentar_el_mismo_clic_porque_la_pantalla_no_cambio_se_permite():
    s = sup()
    modal = vista("Novedades de la versión 4.2", "Actualizamos el sistema", "Entendido")
    assert hacer(s, clic(3), modal, cambio=False).ok     # el primer clic se ignoró
    assert hacer(s, clic(3), modal, cambio=False).ok     # reintentar es lo correcto


def test_llenar_un_formulario_con_tab_y_texto_no_es_un_ciclo():
    s = sup()
    form = vista("Crear cliente", "Razón social o nombre *", "NIT *", "Teléfono *", "Aplicar", "Cerrar")
    tab = Decision(razon="r", accion="tecla", tecla="tab")
    for texto in ("Papelería Los Andes", "901234567", "3157654321"):
        assert hacer(s, Decision(razon="r", accion="escribir", texto=texto), form).ok
        assert hacer(s, tab, form).ok


# ---------------------------------------------------------------- el agente completo
class VncFalso:
    ancho, alto = 1280, 800

    def __init__(self):
        self.acciones = []
        self.reconexiones = 0

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


def test_el_agente_sale_del_ciclo_y_la_ia_recibe_la_prohibicion(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_TOKEN", "t-prueba-123")
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    cfg = Config.desde_entorno()
    vnc = VncFalso()

    async def conectar(*a, **k):
        return vnc

    # pantallas que el escritorio devuelve tras cada acción ejecutada
    secuencia = [LISTA, DETALLE, LISTA, LISTA, DETALLE, DETALLE, DETALLE]
    cola = list(secuencia)

    async def mirar(*a, **k):
        v = cola.pop(0)
        return Vista(imagen=v.imagen, elementos=v.elementos)

    monkeypatch.setattr(agente.Vnc, "conectar", staticmethod(conectar))
    monkeypatch.setattr(agente, "mirar", mirar)

    def resp(**campos):
        base = {"razon": "r"}
        base.update(campos)
        return RespuestaLlm(Decision.model_validate(base), 0.001, True, 10, 5, "falso")

    guion = [
        resp(accion="clic", numero=2),      # abre C-1460          (LISTA)
        resp(accion="clic", numero=3),      # Cerrar               (DETALLE)
        resp(accion="clic", numero=3),      # Filtrar              (LISTA)
        resp(accion="clic", numero=2),      # abre C-1460 otra vez (LISTA)
        resp(accion="clic", numero=3),      # Cerrar otra vez      -> PROHIBIDO
        resp(accion="scroll", direccion="abajo"),   # prueba otra cosa
        resp(accion="terminar", estado="fallida", resumen="No encontré el motivo en la cita."),
    ]
    mensajes = []

    class AgenteGuion(Agente):
        async def decidir(self, llm, mensaje, vista):
            mensajes.append(mensaje)
            return guion.pop(0)

    prog = Progreso()
    res = asyncio.run(AgenteGuion(cfg).ejecutar(
        TAREA, "wss://x/websockify", "clave-123", prog, Bitacora(tmp_path / "b", [])))

    assert res.estado == "fallida"
    clics = [a for a in vnc.acciones if a[0] == "clic"]
    assert len(clics) == 4 and ("scroll",) in vnc.acciones      # el 5.º clic nunca se ejecutó
    assert len(vnc.acciones) == 5
    assert "SECUENCIAS PROHIBIDAS" not in mensajes[4]            # aún no se había detectado
    assert "SECUENCIAS PROHIBIDAS" in mensajes[5] and "C-1460" in mensajes[5]
    assert "PROHIBIDA" in mensajes[5]                            # el aviso del rechazo también llega
