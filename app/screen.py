"""Ver la pantalla: capturar hasta que esté quieta y leer sus textos con Tesseract.

El resultado es una lista de textos numerados con su posición; la IA elige por número
(las IA baratas fallan por unos píxeles si tienen que adivinar coordenadas).
"""
import asyncio
import io
import time
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from PIL import Image

from app.config import Config
from app.vnc import Vnc

# Un píxel cuenta como "distinto" si algún canal cambia más que esto.
_UMBRAL_PIXEL = 24
# Mínimo de píxeles distintos para decir que la pantalla "cambió" (un foco de campo ya los supera).
_MIN_PIXELES_CAMBIO = 20
# Palabras de una misma línea se unen si el hueco entre ellas es menor que esta cantidad de alturas.
_HUECO_MAX_ALTURAS = 1.2
_CONFIANZA_MIN = 30


@dataclass(frozen=True)
class Elemento:
    n: int
    texto: str
    x: int  # esquina izquierda-arriba
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


@dataclass
class Vista:
    imagen: np.ndarray
    elementos: list[Elemento] = field(default_factory=list)
    quieta: bool = True    # False si se agotó el tope sin que dos capturas coincidieran
    cambio: bool = True    # False si se pidió cambio y la pantalla sigue igual a la de antes
    espera_s: float = 0.0
    ocr_s: float = 0.0

    def por_numero(self, n: int) -> Elemento | None:
        for e in self.elementos:
            if e.n == n:
                return e
        return None

    def lista_texto(self) -> str:
        """Lista numerada para la IA: `12 | x=345 y=200 | Nuevo cliente`."""
        return "\n".join(f"{e.n} | x={e.cx} y={e.cy} | {e.texto}" for e in self.elementos)


def fraccion_distinta(a: np.ndarray, b: np.ndarray) -> float:
    """Fracción de píxeles que cambian de verdad entre dos capturas (0.0 a 1.0)."""
    if a.shape != b.shape:
        return 1.0
    dif = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > _UMBRAL_PIXEL
    return float(dif.mean())


def hay_cambio(a: np.ndarray, b: np.ndarray) -> bool:
    if a.shape != b.shape:
        return True
    dif = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2) > _UMBRAL_PIXEL
    return int(dif.sum()) >= _MIN_PIXELES_CAMBIO


async def capturar_quieta(
    vnc: Vnc, cfg: Config, antes: np.ndarray | None = None, exigir_cambio: bool = False
) -> tuple[np.ndarray, bool, bool, float]:
    """Captura hasta que dos capturas seguidas sean casi iguales (cursor parpadeando no cuenta).

    Con `exigir_cambio`, además la pantalla debe diferir de `antes`: después de un clic, dos
    capturas viejas serían iguales entre sí y engañarían. Hay un tope de `screen_stable_max_s`.
    Devuelve (imagen, quieta, cambio, segundos).
    """
    t0 = time.perf_counter()
    await asyncio.sleep(cfg.screen_first_wait_s)
    actual = await vnc.capturar()
    quieta = False
    while True:
        transcurrido = time.perf_counter() - t0
        cambio = antes is None or hay_cambio(antes, actual)
        if transcurrido >= cfg.screen_stable_max_s:
            break
        await asyncio.sleep(cfg.screen_poll_s)
        siguiente = await vnc.capturar()
        coincide = fraccion_distinta(actual, siguiente) < cfg.screen_stable_diff
        actual = siguiente
        cambio = antes is None or hay_cambio(antes, actual)
        if coincide and (cambio or not exigir_cambio):
            quieta = True
            break
    return actual, quieta, cambio, time.perf_counter() - t0


def _agrupar(datos: dict) -> list[tuple[str, int, int, int, int]]:
    """Une palabras de Tesseract en frases por línea; un hueco grande separa celdas distintas."""
    lineas: dict[tuple[int, int, int], list[tuple[int, int, int, int, str]]] = {}
    for i, txt in enumerate(datos["text"]):
        txt = txt.strip()
        try:
            conf = float(datos["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not txt or conf < _CONFIANZA_MIN:
            continue
        clave = (datos["block_num"][i], datos["par_num"][i], datos["line_num"][i])
        lineas.setdefault(clave, []).append(
            (datos["left"][i], datos["top"][i], datos["width"][i], datos["height"][i], txt)
        )
    frases: list[tuple[str, int, int, int, int]] = []
    for palabras in lineas.values():
        palabras.sort(key=lambda p: p[0])
        grupo = [palabras[0]]
        for p in palabras[1:]:
            ult = grupo[-1]
            hueco = p[0] - (ult[0] + ult[2])
            if hueco > _HUECO_MAX_ALTURAS * max(ult[3], p[3]):
                frases.append(_cerrar(grupo))
                grupo = [p]
            else:
                grupo.append(p)
        frases.append(_cerrar(grupo))
    return frases


def _cerrar(grupo: list[tuple[int, int, int, int, str]]) -> tuple[str, int, int, int, int]:
    x0 = min(p[0] for p in grupo)
    y0 = min(p[1] for p in grupo)
    x1 = max(p[0] + p[2] for p in grupo)
    y1 = max(p[1] + p[3] for p in grupo)
    return " ".join(p[4] for p in grupo), x0, y0, x1 - x0, y1 - y0


def leer_textos(imagen: np.ndarray, lang: str, escala: float = 2.0) -> list[Elemento]:
    """Tesseract sobre la captura. Numera de arriba hacia abajo y de izquierda a derecha.

    Se amplía la captura antes de leer (medido: a 2x acierta más textos que a 1x); las
    posiciones se devuelven en píxeles de la pantalla real.
    """
    img = Image.fromarray(imagen)
    if escala != 1:
        img = img.resize((int(img.width * escala), int(img.height * escala)), Image.LANCZOS)
    datos = pytesseract.image_to_data(
        img, lang=lang, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    frases = [
        (t, round(x / escala), round(y / escala), round(w / escala), round(h / escala))
        for t, x, y, w, h in _agrupar(datos)
    ]
    # Filas: agrupa por franja vertical de ~10 px para que "arriba a abajo" no dependa de 1-2 px.
    frases.sort(key=lambda f: (round(f[2] / 10), f[1]))
    return [Elemento(n=i + 1, texto=t, x=x, y=y, w=w, h=h) for i, (t, x, y, w, h) in enumerate(frases)]


async def mirar(
    vnc: Vnc, cfg: Config, antes: np.ndarray | None = None, exigir_cambio: bool = False
) -> Vista:
    """Capturar hasta que esté quieta y leer los textos (Tesseract va en otro hilo)."""
    imagen, quieta, cambio, espera = await capturar_quieta(vnc, cfg, antes, exigir_cambio)
    t0 = time.perf_counter()
    elementos = await asyncio.to_thread(leer_textos, imagen, cfg.ocr_lang, cfg.ocr_scale)
    return Vista(imagen=imagen, elementos=elementos, quieta=quieta, cambio=cambio,
                 espera_s=espera, ocr_s=time.perf_counter() - t0)


def a_png(imagen: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(imagen).save(buf, format="PNG", optimize=False)
    return buf.getvalue()
