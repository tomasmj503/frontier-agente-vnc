"""Bitácora por tarea: cada paso con su captura y su decisión, en logs/<task_id>/.

Nada de lo que se escribe aquí lleva secretos (todo pasa por el filtro).
"""
import json
from pathlib import Path

import numpy as np

from app.screen import a_png
from app.secretos import ocultar


class Bitacora:
    def __init__(self, carpeta: Path, secretos: list[str]):
        self.carpeta = carpeta
        self.secretos = secretos
        try:
            carpeta.mkdir(parents=True, exist_ok=True)
        except OSError:
            self.carpeta = None  # la bitácora nunca debe tumbar la tarea

    def _json(self, nombre: str, datos: dict) -> None:
        if self.carpeta is None:
            return
        try:
            texto = json.dumps(datos, ensure_ascii=False, indent=2, default=str)
            (self.carpeta / nombre).write_text(ocultar(texto, self.secretos), encoding="utf-8")
        except OSError:
            pass

    def paso(self, n: int, imagen: np.ndarray | None, datos: dict) -> None:
        if self.carpeta is None:
            return
        if imagen is not None:
            try:
                (self.carpeta / f"paso_{n:02d}.png").write_bytes(a_png(imagen))
            except OSError:
                pass
        self._json(f"paso_{n:02d}.json", datos)

    def cierre(self, datos: dict) -> None:
        self._json("resumen.json", datos)
