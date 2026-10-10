"""Servicio web del agente. Contrato oficial en BRIEF.md.

Todas las rutas exigen `Authorization: Bearer <TEAM_TOKEN>`.
"""
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import Config


def crear_app(config: Config | None = None) -> FastAPI:
    cfg = config or Config.desde_entorno()
    app = FastAPI(title="Agente que opera programas sin API")

    def exigir_token(authorization: str | None = Header(default=None)) -> None:
        esperado = f"Bearer {cfg.team_token}"
        if not authorization or not secrets.compare_digest(authorization, esperado):
            raise HTTPException(status_code=401, detail="token inválido")

    @app.get("/health", dependencies=[Depends(exigir_token)])
    def health() -> dict:
        return {"ok": True}

    return app
