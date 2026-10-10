"""Servicio web del agente. Contrato oficial en BRIEF.md.

Todas las rutas exigen `Authorization: Bearer <TEAM_TOKEN>`.
"""
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.config import Config
from app.tasks import Gestor


class Escritorio(BaseModel):
    url: str = Field(min_length=1)
    password: str


class NuevaTarea(BaseModel):
    tarea: str = Field(min_length=1)
    escritorio: Escritorio


def crear_app(config: Config | None = None, gestor: Gestor | None = None) -> FastAPI:
    cfg = config or Config.desde_entorno()
    gestor_ = gestor or Gestor(cfg)

    app = FastAPI(title="Agente que opera programas sin API")

    def exigir_token(authorization: str | None = Header(default=None)) -> None:
        esperado = f"Bearer {cfg.team_token}"
        if not authorization or not secrets.compare_digest(authorization, esperado):
            raise HTTPException(status_code=401, detail="token inválido")

    @app.get("/health", dependencies=[Depends(exigir_token)])
    def health() -> dict:
        return {"ok": True}

    @app.post("/tasks", dependencies=[Depends(exigir_token)])
    async def crear_tarea(cuerpo: NuevaTarea) -> dict:
        t = gestor_.crear(cuerpo.tarea, cuerpo.escritorio.url, cuerpo.escritorio.password)
        return {"task_id": t.id}

    @app.get("/tasks/{task_id}", dependencies=[Depends(exigir_token)])
    def estado_tarea(task_id: str) -> dict:
        t = gestor_.obtener(task_id)
        if t is None:
            raise HTTPException(status_code=404, detail="tarea no encontrada")
        return {"estado": t.estado, "resumen": t.resumen}

    @app.get("/tasks/{task_id}/detalle", dependencies=[Depends(exigir_token)])
    def detalle_tarea(task_id: str) -> dict:
        """Extra para bench.py (el contrato oficial solo usa estado y resumen)."""
        t = gestor_.obtener(task_id)
        if t is None:
            raise HTTPException(status_code=404, detail="tarea no encontrada")
        return {
            "estado": t.estado, "segundos": round(t.segundos, 1),
            "costo_usd": round(t.progreso.costo_usd, 6), "pasos": t.progreso.pasos,
            "llamadas_ia": t.progreso.llamadas_ia,
            "seg_espera_pantalla": round(t.progreso.seg_espera, 1),
            "seg_leer_textos": round(t.progreso.seg_ocr, 1),
            "seg_ia": round(t.progreso.seg_ia, 1),
            "seg_acciones": round(t.progreso.seg_accion, 1),
        }

    return app
