"""Gestor de tareas: una sola tarea activa por escritorio, con topes de tiempo y de gasto.

- Si llega una tarea nueva para el mismo escritorio, la anterior se detiene (para que nada
  de lo que haga caiga en la tarea siguiente).
- Al reportar `terminada` o `fallida`, el agente ya cerró su conexión: no queda nada corriendo.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field

from app.agent import Agente, Progreso
from app.bitacora import Bitacora
from app.config import Config
from app.secretos import ocultar

EN_CURSO = "en_curso"
TERMINADA = "terminada"
FALLIDA = "fallida"
MAX_TAREAS_EN_MEMORIA = 200


@dataclass
class Tarea:
    id: str
    texto: str
    escritorio: str          # URL del escritorio (identifica "el mismo escritorio")
    estado: str = EN_CURSO
    resumen: str = ""
    progreso: Progreso = field(default_factory=Progreso)
    segundos: float = 0.0
    _corutina: "asyncio.Task | None" = None


class Gestor:
    def __init__(self, cfg: Config, agente: Agente | None = None):
        self.cfg = cfg
        self.agente = agente or Agente(cfg)
        self._tareas: dict[str, Tarea] = {}
        self._activa_por_escritorio: dict[str, str] = {}
        self.gastado_total_usd = 0.0

    # ------------------------------------------------------------ API
    def crear(self, texto: str, url: str, password: str) -> Tarea:
        """Registra la tarea y la lanza en segundo plano. Vuelve de inmediato."""
        previa_id = self._activa_por_escritorio.get(url)
        if previa_id:
            previa = self._tareas.get(previa_id)
            if previa and previa.estado == EN_CURSO and previa._corutina:
                previa._corutina.cancel()  # se detiene antes de enviar otra acción

        t = Tarea(id=uuid.uuid4().hex[:12], texto=texto, escritorio=url)
        self._tareas[t.id] = t
        self._activa_por_escritorio[url] = t.id
        self._podar()
        t._corutina = asyncio.create_task(self._correr(t, password))
        return t

    def obtener(self, tarea_id: str) -> Tarea | None:
        return self._tareas.get(tarea_id)

    # ------------------------------------------------------------ interno
    async def _correr(self, t: Tarea, password: str) -> None:
        secretos = [password, self.cfg.team_token, self.cfg.openrouter_api_key]
        bitacora = Bitacora(self.cfg.logs_dir / t.id, secretos)
        inicio = time.perf_counter()
        estado, resumen = FALLIDA, "Error interno."
        try:
            tope = self.cfg.openrouter_budget_usd
            if tope > 0 and self.gastado_total_usd >= tope:
                estado, resumen = FALLIDA, "Presupuesto de IA agotado; no se ejecutó la tarea."
            else:
                async with asyncio.timeout(self.cfg.task_max_seconds):
                    r = await self.agente.ejecutar(t.texto, t.escritorio, password, t.progreso, bitacora)
                estado, resumen = r.estado, r.resumen
        except TimeoutError:
            hecho = "; ".join(t.progreso.historial[-6:]) or "no alcancé a hacer nada"
            estado = FALLIDA
            resumen = (f"Llegué al tope de tiempo ({int(self.cfg.task_max_seconds)} s). "
                       f"Lo último que hice: {hecho}.")
        except asyncio.CancelledError:
            estado = FALLIDA
            resumen = "Detenida: llegó una tarea nueva para el mismo escritorio."
        except Exception as e:  # nunca dejar una tarea en_curso para siempre
            estado, resumen = FALLIDA, f"Error interno: {type(e).__name__}."
        finally:
            t.segundos = time.perf_counter() - inicio
            self.gastado_total_usd += t.progreso.costo_usd
            t.resumen = ocultar(resumen, secretos)
            t.estado = estado if estado in (TERMINADA, FALLIDA) else FALLIDA
            if self._activa_por_escritorio.get(t.escritorio) == t.id:
                del self._activa_por_escritorio[t.escritorio]
            bitacora.cierre({
                "task_id": t.id, "tarea": t.texto, "estado": t.estado, "resumen": t.resumen,
                "segundos": round(t.segundos, 1), "costo_usd": t.progreso.costo_usd,
                "pasos": t.progreso.pasos, "llamadas_ia": t.progreso.llamadas_ia,
                "seg_espera_pantalla": round(t.progreso.seg_espera, 1),
                "seg_leer_textos": round(t.progreso.seg_ocr, 1),
                "seg_ia": round(t.progreso.seg_ia, 1),
                "seg_acciones": round(t.progreso.seg_accion, 1),
                "historial": t.progreso.historial, "notas": t.progreso.notas,
            })

    def _podar(self) -> None:
        if len(self._tareas) <= MAX_TAREAS_EN_MEMORIA:
            return
        for k in [k for k, v in self._tareas.items() if v.estado != EN_CURSO][:50]:
            del self._tareas[k]
