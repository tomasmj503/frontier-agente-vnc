"""Supervisor: revisa cada decisión de la IA ANTES de actuar. Las reglas importantes viven aquí,
en código, y no solo en las instrucciones a la IA.

Si algo no cuadra, rechaza la decisión con un aviso (la IA decide de nuevo, sin tocar la pantalla).
"""
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.llm import Decision
from app.screen import Vista
from app.secretos import contiene_secreto

# Teclas que el programa de práctica bloquea o que dejan la pantalla en mal estado.
TECLAS_BLOQUEADAS = {"ctrl+l", "f12", "esc", "escape"}

_SENAL_ERROR = re.compile(r"inv[aá]lid|error|obligatori|no se pudo|ya existe|duplicad", re.I)
_LINEA_RESPUESTA = re.compile(r"^\s*respuesta\s*:", re.I | re.M)
_ES_PREGUNTA = re.compile(r"\?|¿|\bcu[aá]nt[oa]s?\b|\bcu[aá]l(es)?\b|\bqu[ée]\b", re.I)
_ES_CONTEO = re.compile(r"\bcu[aá]nt[oa]s?\b|\bn[uú]mero\s+de\b|\bcantidad\b|\btotal\s+de\b", re.I)
# "Página 2", "Pág. 2 de 5", "Página 2/5"
_PAGINA = re.compile(r"p[áa]g(?:ina|\.)?\s*(\d+)(?:\s*(?:de|/)\s*(\d+))?", re.I)
# Totales que muestra el propio programa: "45 registros", "Total: 45", "de 45 resultados"
_TOTAL_PROGRAMA = re.compile(
    r"\b(?:total|registros|resultados)(?:\s+de\s+\w+)?\s*[:=]\s*(\d[\d.,]*)"
    r"|(\d[\d.,]*)\s+(?:registros|resultados|coincidencias|encontrad[oa]s)\b"
    r"|\bde\s+(\d[\d.,]*)\s+(?:registros|resultados)\b", re.I)
_CONFIRMA_UNICA = re.compile(
    r"\b(?:[uú]nica|sola)\s+p[áa]gina\b|\bno hay m[áa]s p[áa]ginas\b|\b[uú]ltima p[áa]gina\b", re.I)
_NUMERO = re.compile(r"\d[\d.,]*")
# Botones que guardan: nombres distintos según el programa y la versión.
_PALABRAS_APLICAR = re.compile(
    r"\b(?:guardar|aplicar|grabar|salvar|actualizar|registrar|enviar|confirmar)\b", re.I)
# Señales de que el guardado se hizo (aviso, mensaje de éxito).
_CONFIRMACION = re.compile(
    r"cambios aplicados|\bguardad[oa]s?\b|\baplicad[oa]s?\b|\bactualizad[oa]s?\b|\bregistrad[oa]s?\b|"
    r"\bcread[oa]\b|correctamente|[eé]xito|exitos[oa]", re.I)
MAX_RECHAZOS_CONTEO = 2
# Ciclos: se busca una secuencia de 2 a MAX_LARGO_CICLO acciones que se repite sobre la misma pantalla.
MAX_LARGO_CICLO = 6
UMBRAL_PANTALLA_IGUAL = 0.85   # parecido (Jaccard) de los textos para decir "es la misma pantalla"
UMBRAL_TEXTO_IGUAL = 0.85      # parecido de dos textos de botón/enlace leídos con ruido de lectura
MAX_PROHIBIDAS = 3


def _n(texto: str) -> str:
    """Minúsculas, sin tildes y solo letras, números y espacios (para comparar textos leídos)."""
    sin = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", sin).strip()


def _estado(vista: Vista) -> frozenset[str]:
    """Huella de una pantalla: el conjunto de sus textos normalizados (sin posiciones ni números)."""
    return frozenset(t for t in (_n(e.texto) for e in vista.elementos) if len(t) >= 2)


def _misma_pantalla(a: frozenset[str], b: frozenset[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= UMBRAL_PANTALLA_IGUAL


def _misma_firma(a: tuple[str, str], b: tuple[str, str]) -> bool:
    if a[0] != b[0]:
        return False
    if a[1] == b[1]:
        return True
    if min(len(a[1]), len(b[1])) < 4:
        return False
    return SequenceMatcher(None, a[1], b[1]).ratio() >= UMBRAL_TEXTO_IGUAL


@dataclass
class _Paso:
    firma: tuple[str, str]      # (tipo, destino): lo que se hizo, sin números ni posiciones
    etiqueta: str               # texto legible para avisar a la IA
    estado: frozenset[str]      # pantalla en la que se decidió
    cambio: bool | None = None  # ¿la pantalla cambió después de actuar?


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
    # Paginación y totales que el programa mostró (para no dar por bueno un conteo a ojo)
    _paginas_vistas: set[int] = field(default_factory=set)
    _total_paginas: int = 0
    _hay_paginacion: bool = False
    _totales: set[str] = field(default_factory=set)
    _rechazos_conteo: int = 0
    # Guardado sin que el formulario se cierre: una sola vez por registro y confirmado en pantalla
    _aplicado: bool = False
    _confirmacion_vista: bool = False
    _avisos_confirmacion: int = 0
    # Ciclos: historial semántico de lo ejecutado y secuencias ya prohibidas (se le muestran a la IA)
    _historial: list[_Paso] = field(default_factory=list)
    prohibidas: list[str] = field(default_factory=list)

    def registrar_resultado(self, cambio: bool) -> None:
        """El agente avisa si la pantalla cambió tras ejecutar la última acción aprobada."""
        if self._historial:
            self._historial[-1].cambio = cambio

    def descartar_ultima(self) -> None:
        """La última acción aprobada no llegó a ejecutarse (por ejemplo, no se halló el botón)."""
        if self._historial:
            self._historial.pop()

    @staticmethod
    def _firma_semantica(d: Decision, vista: Vista) -> tuple[tuple[str, str], str] | None:
        """Qué se hizo en términos de la app (texto del botón o enlace), no de números de la lista."""
        if d.accion == "clic":
            e = vista.por_numero(d.numero)
            if e is None:
                return None
            texto = _n(e.texto) or f"pos{e.cx // 40}_{e.cy // 24}"
            return ("clic", texto), f"clic en «{e.texto.strip() or texto}»"
        if d.accion == "clic_zona":
            return ("clic", _n(d.texto)), f"clic en «{d.texto.strip()}»"
        if d.accion == "escribir":
            campo = vista.por_numero(d.en) if d.en > 0 else None
            etiqueta = campo.texto if campo is not None else "campo enfocado"
            return ("escribir", f"{_n(d.texto)}@{_n(etiqueta)}"), f"escribir «{d.texto}» en {etiqueta}"
        if d.accion == "tecla":
            return ("tecla", d.tecla.lower().replace(" ", "")), f"tecla {d.tecla}"
        if d.accion == "scroll":
            return ("scroll", d.direccion), f"scroll {d.direccion}"
        return None

    def _detectar_ciclo(self, firma: tuple[str, str], estado: frozenset[str]) -> list[str] | None:
        """¿La acción propuesta completa una secuencia que ya se hizo antes sobre la misma pantalla?

        Se compara la cola del historial más la acción propuesta (de 2 a 6 acciones) con un tramo
        anterior que no se solape. Hace falta que: las acciones coincidan, la pantalla donde empezó
        cada tramo sea la misma (se volvió al mismo lugar), haya al menos un clic y no sea la misma
        acción repetida (eso, como Siguiente varias veces, es avanzar por páginas).
        Dos registros distintos (otro código en el título o en los campos) son pantallas distintas.
        """
        h = self._historial
        n = len(h)
        for largo in range(MAX_LARGO_CICLO, 1, -1):
            if n < 2 * largo - 1:
                continue
            actual = [p.firma for p in h[n - (largo - 1):]] + [firma]
            etiquetas = [p.etiqueta for p in h[n - (largo - 1):]]
            inicio = h[n - (largo - 1)].estado
            if len({a for a in actual}) < 2 or not any(a[0] == "clic" for a in actual):
                continue
            for i in range(0, n - 2 * largo + 2):
                previo = h[i:i + largo]
                if all(_misma_firma(a, p.firma) for a, p in zip(actual, previo, strict=True)) \
                        and _misma_pantalla(previo[0].estado, inicio):
                    return etiquetas
        return None

    def _observar(self, vista: Vista) -> None:
        """Anota la paginación y los totales que muestra esta pantalla."""
        self._hay_paginacion = False
        for e in vista.elementos:
            m = _PAGINA.search(e.texto)
            if m:
                self._hay_paginacion = True
                self._paginas_vistas.add(int(m.group(1)))
                if m.group(2):
                    self._total_paginas = max(self._total_paginas, int(m.group(2)))
            if re.search(r"\bsiguiente\b", e.texto, re.I):
                self._hay_paginacion = True
            t = _TOTAL_PROGRAMA.search(e.texto)
            if t:
                crudo = next(g for g in t.groups() if g)
                self._totales.add(re.sub(r"\D", "", crudo))
            if self._aplicado and _CONFIRMACION.search(e.texto):
                self._confirmacion_vista = True

    def revisar(self, d: Decision, vista: Vista) -> Veredicto:
        self._observar(vista)
        # 1) Los números tienen que existir en la pantalla actual.
        if d.accion == "clic" and vista.por_numero(d.numero) is None:
            return Veredicto(False, f"El número {d.numero} no existe en la lista de textos de esta pantalla.")
        if d.accion == "escribir" and d.en > 0 and vista.por_numero(d.en) is None:
            return Veredicto(
                False, f"El número {d.en} (campo) no existe en la lista de textos de esta pantalla.")

        # 2) Teclas que no sirven.
        if d.accion == "tecla" and d.tecla.lower().replace(" ", "") in TECLAS_BLOQUEADAS:
            return Veredicto(False, f"La tecla {d.tecla} no sirve en este programa. "
                                    "Para salir de un formulario sin guardar usa su botón de salida "
                                    "(Volver/Cancelar/Cerrar).")

        # 3) Nunca escribir una contraseña o clave en el programa.
        if d.accion == "escribir" and contiene_secreto(d.texto, self.secretos):
            return Veredicto(False, "No debes escribir contraseñas ni claves en el programa.")

        # 3a) Ciclos: repetir una secuencia de acciones sobre la misma pantalla, sin avanzar.
        if d.accion != "terminar":
            sem = self._firma_semantica(d, vista)
            if sem is not None:
                ciclo = self._detectar_ciclo(sem[0], _estado(vista))
                if ciclo is not None:
                    secuencia = " → ".join([*ciclo, sem[1]])
                    if secuencia not in self.prohibidas:
                        self.prohibidas = [*self.prohibidas, secuencia][-MAX_PROHIBIDAS:]
                    return Veredicto(False, (
                        f"Estás repitiendo una secuencia sin avanzar: {secuencia}. Ya la hiciste antes y "
                        "volviste a la misma pantalla, así que repetirla no te dará nada nuevo: esa "
                        "secuencia queda PROHIBIDA. Haz algo distinto: otro botón o enlace de esta "
                        "pantalla, desplazarte (scroll) para ver más contenido o filas, otro menú, o "
                        "leer completo el registro antes de cerrarlo. Si ya probaste todo y no puedes "
                        "llegar al dato, reporta 'fallida' explicando qué intentaste."))

        # 3b) Guardar/aplicar: una sola vez por registro (el formulario puede seguir abierto).
        if d.accion in ("clic", "clic_zona"):
            elemento = vista.por_numero(d.numero) if d.accion == "clic" else None
            texto_boton = elemento.texto if elemento is not None else d.texto
            if _PALABRAS_APLICAR.search(texto_boton):
                if self._aplicado:
                    return Veredicto(False, (
                        "Ya aplicaste los cambios de este registro y el formulario sigue abierto: en "
                        "esta versión es normal, NO es un fallo. No lo pulses otra vez (podría "
                        "duplicar o alterar datos). Confírmalo leyendo la pantalla (aviso de "
                        "confirmación, código asignado o los datos en los campos) y termina. Solo "
                        "repite si cambiaste un campo después."))
                self._aplicado = True
                self._confirmacion_vista = False
                self._avisos_confirmacion = 0
            else:
                self._aplicado = False  # salió de ese contexto: cerrar, menú u otro registro
        elif d.accion == "escribir":
            self._aplicado = False  # cambió un dato: un nuevo guardado ya es legítimo

        # 4) Bucles: la misma acción sobre la misma pantalla, una y otra vez.
        firma = (f"{d.accion}|{d.numero}|{d.texto}|{d.en}|{d.tecla}|{d.direccion}|"
                 f"{d.zona_x}|{d.zona_y}|{hash(vista.lista_texto())}")
        self._firmas.append(firma)
        if d.accion != "terminar" and self._firmas[-3:].count(firma) >= 3:
            return Veredicto(False, "Repetiste la misma acción tres veces sobre la misma pantalla sin "
                                    "resultado. Prueba algo distinto o reporta 'fallida' con la razón.")

        if d.accion == "terminar":
            return self._revisar_cierre(d, vista)
        sem = self._firma_semantica(d, vista)
        if sem is not None:
            self._historial.append(_Paso(sem[0], sem[1], _estado(vista)))
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
            # 5a) Si aplicó cambios y no se ve la confirmación, pedir una verificación (una vez).
            if self._aplicado and not self._confirmacion_vista and self._avisos_confirmacion < 1 \
                    and not _ES_PREGUNTA.search(self.tarea):
                self._avisos_confirmacion += 1
                return Veredicto(False, (
                    "Aplicaste cambios pero no veo una confirmación en la pantalla. Revisa: ¿hay un aviso "
                    "('Cambios aplicados', 'Guardado'), el registro muestra su código o los campos tienen "
                    "los datos pedidos? Si lo confirmas, dilo en el resumen y termina; si hay un error, "
                    "reporta 'fallida'. NO pulses guardar/aplicar otra vez."))
            # 5b) Un conteo no se da "a ojo" si el programa tiene paginación sin recorrer o un total.
            veredicto = self._revisar_conteo(d)
            if veredicto is not None:
                return veredicto
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

    def _revisar_conteo(self, d: Decision) -> Veredicto | None:
        """Regla del DISENO: nunca 'terminada' con un número que no quedó verificado.

        - Si el programa muestra un total ("45 registros"), la respuesta debe ser ese total.
        - Si hay paginación y no se recorrieron las páginas, el conteo es parcial.
        Tras 2 avisos sin resolver, la tarea se reporta 'fallida' explicando por qué.
        """
        if not _ES_CONTEO.search(self.tarea):
            return None
        linea = next((x for x in d.resumen.splitlines() if _LINEA_RESPUESTA.match(x)), None)
        if linea is None:
            return None
        m = _NUMERO.search(linea.split(":", 1)[1])
        dado = re.sub(r"\D", "", m.group(0)) if m else ""

        motivo = ""
        if self._totales and dado not in self._totales:
            motivo = (f"el programa muestra el total {', '.join(sorted(self._totales))} y la "
                      f"respuesta dada ({dado or 'sin número'}) no coincide con él")
        elif self._hay_paginacion and not _CONFIRMA_UNICA.search(d.resumen):
            vistas = sorted(self._paginas_vistas) or [1]
            completo = (self._total_paginas and set(range(1, self._total_paginas + 1)) <= set(vistas)) \
                or (not self._total_paginas and len(vistas) >= 2)
            if not completo:
                motivo = ("hay paginación y solo se revisaron las páginas "
                          f"{', '.join(map(str, vistas))}"
                          + (f" de {self._total_paginas}" if self._total_paginas else "")
                          + ": el conteo es parcial")
        if not motivo:
            return None

        self._rechazos_conteo += 1
        if self._rechazos_conteo > MAX_RECHAZOS_CONTEO:
            return Veredicto(True, decision=d.model_copy(update={
                "estado": "fallida",
                "resumen": f"No pude confirmar el dato pedido: {motivo}. No entrego un número sin verificar.",
            }))
        return Veredicto(False, (
            f"No des 'terminada' todavía: {motivo}. Usa el total o los filtros del programa, o recorre "
            "TODAS las páginas con el botón Siguiente y suma. Si es una sola página, dilo en el resumen "
            "('única página'). Si no puedes llegar al dato, reporta 'fallida' explicando por qué y "
            "sin línea 'respuesta:'."))
