"""Supervisor: revisa cada decisión de la IA ANTES de actuar. Las reglas importantes viven aquí,
en código, y no solo en las instrucciones a la IA.

Si algo no cuadra, rechaza la decisión con un aviso (la IA decide de nuevo, sin tocar la pantalla).
"""
import re
from dataclasses import dataclass, field

from app.llm import Decision
from app.screen import Vista
from app.secretos import contiene_secreto

# Teclas que el programa de práctica bloquea o que dejan la pantalla en mal estado.
TECLAS_BLOQUEADAS = {"ctrl+l", "f12", "esc", "escape"}

_SENAL_ERROR = re.compile(r"inv[aá]lid|error|obligatori|no se pudo|ya existe|duplicad", re.I)
_LINEA_RESPUESTA = re.compile(r"^\s*respuesta\s*:", re.I | re.M)
_ES_PREGUNTA = re.compile(r"\?|¿|\bcu[aá]nt[oa]s?\b|\bcu[aá]l(es)?\b|\bqu[ée]\b", re.I)


@dataclass
class Veredicto:
    ok: bool
    aviso: str = ""
    decision: Decision | None = None  # decisión corregida (cuando aplica)


@dataclass
class Supervisor:
    tarea: str
    secretos: list[str]
    _confirmado_error: bool = False
    _confirmado_pregunta: bool = False
    _firmas: list[str] = field(default_factory=list)

    def revisar(self, d: Decision, vista: Vista) -> Veredicto:
        # 1) Los números tienen que existir en la pantalla actual.
        if d.accion == "clic" and vista.por_numero(d.numero) is None:
            return Veredicto(False, f"El número {d.numero} no existe en la lista de textos de esta pantalla.")
        if d.accion == "escribir" and d.en > 0 and vista.por_numero(d.en) is None:
            return Veredicto(
                False, f"El número {d.en} (campo) no existe en la lista de textos de esta pantalla.")

        # 2) Teclas que no sirven.
        if d.accion == "tecla" and d.tecla.lower().replace(" ", "") in TECLAS_BLOQUEADAS:
            return Veredicto(False, f"La tecla {d.tecla} no sirve en este programa. "
                                    "Para salir de un formulario sin guardar usa el botón 'Volver'.")

        # 3) Nunca escribir una contraseña o clave en el programa.
        if d.accion == "escribir" and contiene_secreto(d.texto, self.secretos):
            return Veredicto(False, "No debes escribir contraseñas ni claves en el programa.")

        # 4) Bucles: la misma acción sobre la misma pantalla, una y otra vez.
        firma = f"{d.accion}|{d.numero}|{d.texto}|{d.en}|{d.tecla}|{d.direccion}|{hash(vista.lista_texto())}"
        self._firmas.append(firma)
        if d.accion != "terminar" and self._firmas[-3:].count(firma) >= 3:
            return Veredicto(False, "Repetiste la misma acción tres veces sobre la misma pantalla sin "
                                    "resultado. Prueba algo distinto o reporta 'fallida' con la razón.")

        if d.accion == "terminar":
            return self._revisar_cierre(d, vista)
        return Veredicto(True)

    def _revisar_cierre(self, d: Decision, vista: Vista) -> Veredicto:
        resumen = d.resumen
        if d.estado == "terminada":
            # 5) No cerrar como 'terminada' con un error a la vista, sin confirmarlo una vez.
            texto = " ".join(e.texto for e in vista.elementos)
            if _SENAL_ERROR.search(texto) and not self._confirmado_error:
                self._confirmado_error = True
                return Veredicto(False, "La pantalla muestra un texto de error o aviso. Revisa que el "
                                        "dato realmente quedó guardado igual a lo pedido antes de "
                                        "dar 'terminada'; si no quedó, reporta 'fallida'.")
            # 6) Una pregunta termina con una línea 'respuesta: ...'.
            if _ES_PREGUNTA.search(self.tarea) and not _LINEA_RESPUESTA.search(resumen) \
                    and not self._confirmado_pregunta:
                self._confirmado_pregunta = True
                return Veredicto(False, "La orden es una pregunta: el resumen debe incluir una línea "
                                        "'respuesta: <valor>' (número primero). Si no se puede "
                                        "responder, reporta 'fallida' sin esa línea.")
        else:
            # 7) Una tarea que falla no lleva línea 'respuesta:'.
            limpio = "\n".join(
                linea for linea in resumen.splitlines() if not _LINEA_RESPUESTA.match(linea)
            )
            if limpio != resumen:
                return Veredicto(True, decision=d.model_copy(update={"resumen": limpio or "Tarea fallida."}))
        return Veredicto(True)
