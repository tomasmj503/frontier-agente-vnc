"""El ciclo del agente: mirar → decidir → supervisor → actuar.

Punto de enchufe para las capas 2 y 3 del diseño (habilidades generales y procedimientos
aprendidos): `Agente.decidir`. Hoy siempre pregunta a la IA; después, antes de preguntarle,
podrá intentar un procedimiento sin IA y usar la IA solo como respaldo.
"""
import asyncio
import re
import time
from dataclasses import dataclass, field

from app.bitacora import Bitacora
from app.config import Config
from app.llm import Decision, ErrorLlm, Llm, RespuestaLlm
from app.screen import Elemento, Vista, mirar
from app.secretos import ocultar
from app.supervisor import Supervisor
from app.vnc import ErrorVnc, Vnc

MAX_RECHAZOS_SEGUIDOS = 4
MAX_FORMATO_SEGUIDOS = 3
MAX_SIN_CAMBIO_SEGUIDOS = 5
MAX_RESUMEN = 1500


@dataclass
class Progreso:
    """Lo que el gestor de tareas puede leer mientras el agente trabaja."""
    historial: list[str] = field(default_factory=list)
    costo_usd: float = 0.0
    pasos: int = 0
    llamadas_ia: int = 0
    inicio: float = field(default_factory=time.perf_counter)
    # Dónde se va el tiempo (segundos): esperar a que la pantalla quede quieta, leer textos,
    # esperar a la IA y ejecutar la acción (clics y teclas).
    seg_espera: float = 0.0
    seg_ocr: float = 0.0
    seg_ia: float = 0.0
    seg_accion: float = 0.0


@dataclass(frozen=True)
class Resultado:
    estado: str   # 'terminada' | 'fallida'
    resumen: str


class Agente:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    # ------------------------------------------------------------ enchufe para capas 2 y 3
    async def decidir(self, llm: Llm, mensaje: str, vista: Vista) -> RespuestaLlm:
        """Hoy: siempre la IA. Aquí se enchufan después procedimientos y habilidades sin IA."""
        from app.screen import a_png
        png = a_png(vista.imagen) if self.cfg.llm_send_image else None
        return await llm.decidir(mensaje, png)

    # ------------------------------------------------------------ ciclo principal
    async def ejecutar(self, tarea: str, url: str, password: str, progreso: Progreso,
                       bitacora: Bitacora) -> Resultado:
        secretos = [password, self.cfg.team_token, self.cfg.openrouter_api_key]
        llm = Llm(self.cfg, secretos)
        supervisor = Supervisor(tarea=tarea, secretos=secretos)

        try:
            vnc = await Vnc.conectar(url, password, self.cfg)
        except ErrorVnc as e:
            return Resultado("fallida", f"No pude conectarme al escritorio: {e}.")

        async with vnc:
            vista = await mirar(vnc, self.cfg)
            progreso.seg_espera += vista.espera_s
            progreso.seg_ocr += vista.ocr_s
            avisos: list[str] = []
            rechazos = 0
            sin_cambio = 0
            formato_malo = 0
            while True:
                if progreso.pasos >= self.cfg.task_max_steps:
                    return self._fallo(
                        progreso, f"Llegué al tope de {self.cfg.task_max_steps} pasos.")
                if progreso.costo_usd >= self.cfg.task_max_cost_usd:
                    return self._fallo(progreso, "Llegué al tope de gasto de la tarea.")
                progreso.pasos += 1
                n = progreso.pasos

                avisos_paso = list(avisos)
                avisos = []
                if not vista.quieta:
                    avisos_paso.append(
                        "La pantalla seguía cambiando cuando la leí; puede estar a medio cargar.")
                msg = llm.mensaje_paso(tarea, progreso.historial, self._lista(vista), avisos_paso)

                t_ia = time.perf_counter()
                try:
                    r = await self.decidir(llm, msg, vista)
                except ErrorLlm as e:
                    progreso.seg_ia += time.perf_counter() - t_ia
                    progreso.costo_usd += e.costo_usd
                    if e.formato:  # respondió mal: se le pide de nuevo, sin tocar la pantalla
                        formato_malo += 1
                        progreso.historial.append(f"{n}. (la IA respondió con formato inválido)")
                        if formato_malo >= MAX_FORMATO_SEGUIDOS:
                            return self._fallo(
                                progreso, f"La IA no logró responder en el formato pedido: {e}")
                        avisos.append("Tu respuesta anterior no cumplió el formato. Responde un objeto "
                                      "válido: un clic lleva 'numero' (de la lista actual), escribir "
                                      "lleva 'texto'.")
                        continue
                    return self._fallo(progreso, f"La IA no pudo decidir: {e}")
                formato_malo = 0
                ia_s = time.perf_counter() - t_ia
                progreso.seg_ia += ia_s
                progreso.costo_usd += r.costo_usd
                progreso.llamadas_ia += 1
                d = r.decision

                v = supervisor.revisar(d, vista)
                if v.decision is not None:
                    d = v.decision
                bitacora.paso(n, vista.imagen, {
                    "paso": n, "decision": d.model_dump(), "rechazada": not v.ok, "aviso": v.aviso,
                    "costo_paso_usd": r.costo_usd, "costo_acumulado_usd": progreso.costo_usd,
                    "ia_s": round(ia_s, 2),
                    "modelo": r.modelo, "tokens": [r.tokens_entrada, r.tokens_salida],
                    "pantalla_quieta": vista.quieta, "espera_s": round(vista.espera_s, 2),
                    "ocr_s": round(vista.ocr_s, 2), "textos": vista.lista_texto(),
                })

                if not v.ok:
                    rechazos += 1
                    progreso.historial.append(f"{n}. (rechazado: {v.aviso})")
                    if rechazos >= MAX_RECHAZOS_SEGUIDOS:
                        return self._fallo(progreso, "No logré una acción válida: " + v.aviso)
                    avisos.append(v.aviso)
                    continue
                rechazos = 0

                if d.accion == "terminar":
                    return Resultado(d.estado, self._limpiar(d.resumen, secretos))

                descripcion = self._describir(d, vista)
                t_acc = time.perf_counter()
                await self._actuar(vnc, d, vista)
                progreso.seg_accion += time.perf_counter() - t_acc
                nueva = await mirar(vnc, self.cfg, antes=vista.imagen, exigir_cambio=(d.accion == "clic"))
                progreso.seg_espera += nueva.espera_s
                progreso.seg_ocr += nueva.ocr_s
                cambio = "la pantalla cambió" if nueva.cambio else "la pantalla NO cambió"
                progreso.historial.append(f"{n}. {descripcion} → {cambio}")
                if nueva.cambio:
                    sin_cambio = 0
                else:
                    sin_cambio += 1
                    avisos.append("La pantalla no cambió después de tu última acción.")
                    if sin_cambio >= MAX_SIN_CAMBIO_SEGUIDOS:
                        return self._fallo(progreso, "La pantalla no respondió a mis acciones.")
                vista = nueva

    # ------------------------------------------------------------ actuar
    async def _actuar(self, vnc: Vnc, d: Decision, vista: Vista) -> None:
        if d.accion == "clic":
            e = vista.por_numero(d.numero)
            assert e is not None  # el supervisor ya lo verificó
            await vnc.clic(e.cx, e.cy)
        elif d.accion == "escribir":
            if d.en > 0:
                e = vista.por_numero(d.en)
                assert e is not None
                x, y = self._punto_campo(e, d.donde)
                await vnc.clic(x, y)
                await asyncio.sleep(0.15)  # que el campo tome el foco antes de escribir
            await vnc.escribir(d.texto, reemplazar=True)
        elif d.accion == "tecla":
            await vnc.tecla(d.tecla)
        elif d.accion == "scroll":
            await vnc.scroll(vnc.ancho // 2, vnc.alto // 2, d.direccion, pasos=5)

    def _punto_campo(self, e: Elemento, donde: str) -> tuple[int, int]:
        if donde == "derecha":
            return int(e.x + e.w + self.cfg.field_offset_x), e.cy
        if donde == "sobre":
            return e.cx, e.cy
        return int(e.x + self.cfg.field_offset_x), int(e.cy + self.cfg.field_offset_y)

    # ------------------------------------------------------------ utilidades
    def _lista(self, vista: Vista) -> str:
        from app.llm import MAX_ELEMENTOS
        filas = [f"{e.n} | x={e.cx} y={e.cy} | {e.texto}" for e in vista.elementos[:MAX_ELEMENTOS]]
        if len(vista.elementos) > MAX_ELEMENTOS:
            filas.append(f"(hay {len(vista.elementos) - MAX_ELEMENTOS} textos más abajo; usa scroll)")
        return "\n".join(filas)

    @staticmethod
    def _describir(d: Decision, vista: Vista) -> str:
        if d.accion == "clic":
            e = vista.por_numero(d.numero)
            return f"clic en {d.numero} «{e.texto if e else '?'}»"
        if d.accion == "escribir":
            if d.en > 0:
                e = vista.por_numero(d.en)
                return f"escribir «{d.texto}» en el campo de «{e.texto if e else '?'}»"
            return f"escribir «{d.texto}» en el campo enfocado"
        if d.accion == "tecla":
            return f"tecla {d.tecla}"
        return f"scroll {d.direccion}"

    @staticmethod
    def _limpiar(resumen: str, secretos: list[str]) -> str:
        texto = ocultar(resumen.strip(), secretos)
        texto = re.sub(r"[ \t]+\n", "\n", texto)
        return texto[:MAX_RESUMEN]

    def _fallo(self, progreso: Progreso, motivo: str) -> Resultado:
        hecho = "; ".join(progreso.historial[-6:]) or "no alcancé a hacer nada"
        return Resultado("fallida", f"{motivo} Lo último que hice: {hecho}.")
