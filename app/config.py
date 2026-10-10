"""Configuración del agente: todo sale de variables de entorno (o del archivo .env).

Lo que puede cambiar si la app cambia (modelo, esperas, clic, topes) vive aquí
y se ajusta en .env, sin tocar código.
"""
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def cargar_env(ruta: Path | None = None) -> None:
    """Lee un archivo .env y lo vuelca a os.environ sin pisar lo que ya esté definido."""
    ruta = ruta or RAIZ / ".env"
    if not ruta.is_file():
        return
    for linea in ruta.read_text().splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip("\"'"))


def _texto(nombre: str, defecto: str | None = None) -> str:
    valor = os.environ.get(nombre, "").strip()
    if valor:
        return valor
    if defecto is None:
        raise RuntimeError(f"Falta {nombre} en .env (no tiene valor por defecto).")
    return defecto


def _numero(nombre: str, defecto: float) -> float:
    crudo = os.environ.get(nombre, "").strip()
    if not crudo:
        return defecto
    try:
        return float(crudo)
    except ValueError:
        raise RuntimeError(f"{nombre} debe ser un número, pero vale {crudo!r}.") from None


def _booleano(nombre: str, defecto: bool) -> bool:
    crudo = os.environ.get(nombre, "").strip().lower()
    if not crudo:
        return defecto
    return crudo in ("1", "true", "si", "sí", "yes")


@dataclass(frozen=True)
class Config:
    # Acceso al servicio
    team_token: str

    # IA (OpenRouter)
    openrouter_api_key: str
    openrouter_budget_usd: float
    llm_model: str
    llm_send_image: bool
    llm_timeout_s: float

    # Topes por tarea
    task_max_seconds: float
    task_max_cost_usd: float
    task_max_steps: int

    # Clic y teclado (milisegundos)
    click_hold_ms: float
    click_move_ms: float
    key_hold_ms: float
    type_hold_ms: float

    # Dónde hacer clic para llegar a un campo desde su etiqueta (píxeles)
    field_offset_y: float   # "debajo": cuántos píxeles bajo el centro de la etiqueta
    field_offset_x: float   # "derecha": cuántos píxeles a la derecha del final de la etiqueta

    # Esperas de pantalla
    screen_stable_diff: float   # fracción de píxeles distintos que se tolera (cursor parpadeando)
    screen_stable_max_s: float  # tope de espera hasta que la pantalla esté quieta
    screen_poll_s: float        # pausa entre capturas
    screen_first_wait_s: float  # pausa antes de la primera captura después de actuar

    # VNC
    vnc_connect_retries: int
    vnc_open_timeout_s: float

    # Lectura de texto
    ocr_lang: str
    ocr_scale: float  # ampliación de la captura antes de leer (medido: 2 lee mejor que 1)

    # Bitácora
    logs_dir: Path

    @classmethod
    def desde_entorno(cls) -> "Config":
        cargar_env()
        return cls(
            team_token=_texto("TEAM_TOKEN"),
            openrouter_api_key=_texto("OPENROUTER_API_KEY", ""),
            openrouter_budget_usd=_numero("OPENROUTER_BUDGET_USD", 0.0),
            llm_model=_texto("LLM_MODEL", "google/gemini-3.8-flash"),
            llm_send_image=_booleano("LLM_SEND_IMAGE", True),
            llm_timeout_s=_numero("LLM_TIMEOUT_S", 60),
            task_max_seconds=_numero("TASK_MAX_SECONDS", 270),
            task_max_cost_usd=_numero("TASK_MAX_COST_USD", 0.15),
            task_max_steps=int(_numero("TASK_MAX_STEPS", 40)),
            click_hold_ms=_numero("CLICK_HOLD_MS", 150),
            click_move_ms=_numero("CLICK_MOVE_MS", 100),
            key_hold_ms=_numero("KEY_HOLD_MS", 50),
            type_hold_ms=_numero("TYPE_HOLD_MS", 30),
            field_offset_y=_numero("FIELD_OFFSET_Y", 18),
            field_offset_x=_numero("FIELD_OFFSET_X", 25),
            screen_stable_diff=_numero("SCREEN_STABLE_DIFF", 0.01),
            screen_stable_max_s=_numero("SCREEN_STABLE_MAX_S", 3),
            screen_poll_s=_numero("SCREEN_POLL_S", 0.4),
            screen_first_wait_s=_numero("SCREEN_FIRST_WAIT_S", 0.6),
            vnc_connect_retries=int(_numero("VNC_CONNECT_RETRIES", 1)),
            vnc_open_timeout_s=_numero("VNC_OPEN_TIMEOUT_S", 20),
            ocr_lang=_texto("OCR_LANG", "spa"),
            ocr_scale=_numero("OCR_SCALE", 2),
            logs_dir=RAIZ / _texto("LOGS_DIR", "logs"),
        )
