"""Pruebas del contrato del BRIEF: token, formas de respuesta, < 2 s y una tarea por escritorio."""
import asyncio
import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from app.agent import Resultado
from app.config import Config
from app.main import crear_app
from app.tasks import Gestor

TOKEN = "token-de-prueba-123"
CLAVE_ESCRITORIO = "clave-escritorio-xyz"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class AgenteFalso:
    """Agente de mentira: espera `demora` segundos y devuelve lo que se le pida."""

    def __init__(self, demora=0.0, resultado=None):
        self.demora = demora
        self.resultado = resultado or Resultado("terminada", "Hecho.")
        self.llamadas = 0

    async def ejecutar(self, tarea, url, password, progreso, bitacora):
        self.llamadas += 1
        progreso.pasos = 1
        await asyncio.sleep(self.demora)
        return self.resultado


@pytest.fixture
def cfg(monkeypatch, tmp_path):
    monkeypatch.setenv("TEAM_TOKEN", TOKEN)
    monkeypatch.setenv("LOGS_DIR", str(tmp_path / "logs"))
    return Config.desde_entorno()


def cuerpo(url="wss://escritorio-a/websockify"):
    return {"tarea": "Haz algo.", "escritorio": {"url": url, "password": CLAVE_ESCRITORIO}}


def esperar_fin(client, task_id, maximo=5.0):
    fin = time.time() + maximo
    while time.time() < fin:
        r = client.get(f"/tasks/{task_id}", headers=AUTH).json()
        if r["estado"] != "en_curso":
            return r
        time.sleep(0.05)
    raise AssertionError("la tarea no terminó a tiempo")


def test_health_exige_token(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso()))) as c:
        assert c.get("/health").status_code == 401
        assert c.get("/health", headers={"Authorization": "Bearer malo"}).status_code == 401
        r = c.get("/health", headers=AUTH)
        assert r.status_code == 200 and r.json() == {"ok": True}


def test_todas_las_rutas_exigen_token(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso()))) as c:
        assert c.post("/tasks", json=cuerpo()).status_code == 401
        assert c.get("/tasks/abc").status_code == 401


def test_post_tasks_responde_rapido_y_get_da_estado(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso(demora=1.0)))) as c:
        t0 = time.perf_counter()
        r = c.post("/tasks", headers=AUTH, json=cuerpo())
        assert time.perf_counter() - t0 < 2
        assert r.status_code == 200
        assert set(r.json()) == {"task_id"}
        tid = r.json()["task_id"]
        g = c.get(f"/tasks/{tid}", headers=AUTH).json()
        assert g == {"estado": "en_curso", "resumen": ""}
        fin = esperar_fin(c, tid)
        assert fin == {"estado": "terminada", "resumen": "Hecho."}


def test_cuerpo_invalido_y_tarea_inexistente(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso()))) as c:
        assert c.post("/tasks", headers=AUTH, json={"tarea": "x"}).status_code == 422
        assert c.get("/tasks/no-existe", headers=AUTH).status_code == 404


def test_una_tarea_nueva_detiene_la_anterior_del_mismo_escritorio(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso(demora=5.0)))) as c:
        a = c.post("/tasks", headers=AUTH, json=cuerpo()).json()["task_id"]
        b = c.post("/tasks", headers=AUTH, json=cuerpo()).json()["task_id"]
        fin_a = esperar_fin(c, a)
        assert fin_a["estado"] == "fallida" and "Detenida" in fin_a["resumen"]
        assert c.get(f"/tasks/{b}", headers=AUTH).json()["estado"] == "en_curso"


def test_escritorios_distintos_no_se_estorban(cfg):
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso(demora=0.5)))) as c:
        a = c.post("/tasks", headers=AUTH, json=cuerpo("wss://uno/websockify")).json()["task_id"]
        b = c.post("/tasks", headers=AUTH, json=cuerpo("wss://dos/websockify")).json()["task_id"]
        assert esperar_fin(c, a)["estado"] == "terminada"
        assert esperar_fin(c, b)["estado"] == "terminada"


def test_tope_de_tiempo_deja_la_tarea_fallida(cfg):
    corto = dataclasses.replace(cfg, task_max_seconds=0.3)
    with TestClient(crear_app(corto, Gestor(corto, AgenteFalso(demora=5.0)))) as c:
        tid = c.post("/tasks", headers=AUTH, json=cuerpo()).json()["task_id"]
        fin = esperar_fin(c, tid)
        assert fin["estado"] == "fallida" and "tope de tiempo" in fin["resumen"]


def test_el_resumen_nunca_lleva_la_clave_del_escritorio(cfg):
    malo = Resultado("terminada", f"Listo, la clave es {CLAVE_ESCRITORIO} y el token {TOKEN}.")
    with TestClient(crear_app(cfg, Gestor(cfg, AgenteFalso(resultado=malo)))) as c:
        tid = c.post("/tasks", headers=AUTH, json=cuerpo()).json()["task_id"]
        fin = esperar_fin(c, tid)
        assert CLAVE_ESCRITORIO not in fin["resumen"] and TOKEN not in fin["resumen"]
        assert "[oculto]" in fin["resumen"]


def test_el_agente_que_falla_deja_estado_fallida(cfg):
    class AgenteRoto:
        async def ejecutar(self, *a, **k):
            raise RuntimeError("boom")

    with TestClient(crear_app(cfg, Gestor(cfg, AgenteRoto()))) as c:
        tid = c.post("/tasks", headers=AUTH, json=cuerpo()).json()["task_id"]
        fin = esperar_fin(c, tid)
        assert fin["estado"] == "fallida" and "RuntimeError" in fin["resumen"]
