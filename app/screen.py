"""Ver la pantalla: capturar hasta que esté quieta y leer sus textos con Tesseract.

El resultado es una lista de textos numerados con su posición; la IA elige por número
(las IA baratas fallan por unos píxeles si tienen que adivinar coordenadas).
"""
import asyncio
import io
import re
import time
import unicodedata
from difflib import SequenceMatcher
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
# Tope de botones que se leen recortados por pantalla (cada uno cuesta ~0.1 s).
MAX_BOTONES = 12


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


def _comparar(anterior: np.ndarray, nueva: np.ndarray, antes: np.ndarray | None,
              umbral: float) -> tuple[bool, bool]:
    """(¿coincide con la captura anterior?, ¿cambió respecto de `antes`?). Trabajo de numpy: va en un hilo."""
    return fraccion_distinta(anterior, nueva) < umbral, antes is None or hay_cambio(antes, nueva)


async def capturar_quieta(
    vnc: Vnc, cfg: Config, antes: np.ndarray | None = None, exigir_cambio: bool = False
) -> tuple[np.ndarray, bool, bool, float]:
    """Captura hasta que dos capturas seguidas sean casi iguales (cursor parpadeando no cuenta).

    Con `exigir_cambio`, además la pantalla debe diferir de `antes`: después de un clic, dos
    capturas viejas serían iguales entre sí y engañarían. Hay un tope de `screen_stable_max_s`.
    Las comparaciones de imágenes corren en un hilo para no frenar las respuestas del servicio.
    Devuelve (imagen, quieta, cambio, segundos).
    """
    t0 = time.perf_counter()
    await asyncio.sleep(cfg.screen_first_wait_s)
    actual = await vnc.capturar()
    quieta = False
    cambio = antes is None or await asyncio.to_thread(hay_cambio, antes, actual)
    while time.perf_counter() - t0 < cfg.screen_stable_max_s:
        await asyncio.sleep(cfg.screen_poll_s)
        siguiente = await vnc.capturar()
        coincide, cambio = await asyncio.to_thread(
            _comparar, actual, siguiente, antes, cfg.screen_stable_diff)
        actual = siguiente
        if coincide and (cambio or not exigir_cambio):
            quieta = True
            break
    return actual, quieta, cambio, time.perf_counter() - t0


# Bordes de botones y celdas que Tesseract lee como texto: no son parte de la frase, la separan.
_BORDES = "|[]{}()!¡_\\/ "


def _agrupar(datos: dict) -> list[tuple[str, int, int, int, int]]:
    """Une palabras de Tesseract en frases por línea.

    Un hueco grande o un borde de botón (| [ ] ...) separa frases distintas: así dos botones
    pegados ("Nuevo pedido" y "Exportar") no quedan como un solo texto.
    """
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
        grupo: list[tuple[int, int, int, int, str]] = []
        for x, y, w, h, txt in palabras:
            limpio = txt.strip(_BORDES)
            if not limpio:  # solo bordes: corta la frase actual
                if grupo:
                    frases.append(_cerrar(grupo))
                    grupo = []
                continue
            if txt != limpio:  # bordes pegados a la palabra ("|Exportar", "[30/09/2026")
                if txt[0] in _BORDES and grupo:
                    frases.append(_cerrar(grupo))
                    grupo = []
                txt = limpio
            if grupo:
                ult = grupo[-1]
                hueco = x - (ult[0] + ult[2])
                if hueco > _HUECO_MAX_ALTURAS * max(ult[3], h):
                    frases.append(_cerrar(grupo))
                    grupo = []
            grupo.append((x, y, w, h, txt))
        if grupo:
            frases.append(_cerrar(grupo))
    return frases


def _cerrar(grupo: list[tuple[int, int, int, int, str]]) -> tuple[str, int, int, int, int]:
    x0 = min(p[0] for p in grupo)
    y0 = min(p[1] for p in grupo)
    x1 = max(p[0] + p[2] for p in grupo)
    y1 = max(p[1] + p[3] for p in grupo)
    return " ".join(p[4] for p in grupo), x0, y0, x1 - x0, y1 - y0


def _ocr(img: Image.Image, lang: str, escala: float) -> list[tuple[str, int, int, int, int]]:
    datos = pytesseract.image_to_data(
        img, lang=lang, config="--psm 11", output_type=pytesseract.Output.DICT
    )
    return [
        (t, round(x / escala), round(y / escala), round(w / escala), round(h / escala))
        for t, x, y, w, h in _agrupar(datos)
    ]


def _contenida(f: tuple[str, int, int, int, int], caja: tuple[int, int, int, int]) -> bool:
    cx, cy = f[1] + f[3] / 2, f[2] + f[4] / 2
    x, y, w, h = caja
    return x - 2 <= cx <= x + w + 2 and y - 2 <= cy <= y + h + 2


def _componentes(mascara: np.ndarray, min_alto: int = 20) -> list[tuple[int, int, int, int]]:
    """Cajas (x, y, w, h) de las manchas de la máscara con tamaño de botón.

    Une las franjas de píxeles que se tocan de una fila a la siguiente. Se descartan las
    cabeceras y paneles (muy anchos) y las líneas de texto resaltadas (muy bajas).
    """
    alto = mascara.shape[0]
    padre: list[int] = []

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    franjas: list[tuple[int, int, int]] = []  # (fila, x0, x1) por franja
    previas: list[tuple[int, int, int]] = []  # (indice, x0, x1) de la fila anterior
    for fila in range(alto):
        fila_m = mascara[fila]
        actuales: list[tuple[int, int, int]] = []
        if fila_m.any():
            cambios = np.flatnonzero(np.diff(np.concatenate(([0], fila_m.view(np.int8), [0]))))
            for x0, x1 in zip(cambios[0::2], cambios[1::2], strict=True):
                if x1 - x0 < 6:
                    continue
                idx = len(franjas)
                franjas.append((fila, int(x0), int(x1)))
                padre.append(idx)
                for pi, px0, px1 in previas:
                    if px0 < x1 and x0 < px1:
                        padre[raiz(idx)] = raiz(pi)
                actuales.append((idx, int(x0), int(x1)))
        previas = actuales
    cajas: dict[int, list[int]] = {}
    for idx, (fila, x0, x1) in enumerate(franjas):
        c = cajas.setdefault(raiz(idx), [x0, fila, x1, fila + 1, 0])
        c[0], c[1] = min(c[0], x0), min(c[1], fila)
        c[2], c[3] = max(c[2], x1), max(c[3], fila + 1)
        c[4] += x1 - x0
    salida = []
    for x0, y0, x1, y1, pix in cajas.values():
        w, h = x1 - x0, y1 - y0
        if 28 <= w <= 260 and min_alto <= h <= 60 and pix / (w * h) > 0.45:
            salida.append((x0, y0, w, h))
    return salida


def _rectangulos_oscuros(imagen: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Cajas (x, y, w, h) de los botones de fondo azul oscuro (texto blanco).

    Se busca por color: fondo oscuro con más azul que rojo. Los botones grises con borde
    (Siguiente, Limpiar) NO se detectan aquí: se probó un detector por color gris claro y
    empeoraba la lectura al confundirse con las franjas de las tablas (medido).
    """
    r = imagen[:, :, 0].astype(np.int16)
    g = imagen[:, :, 1].astype(np.int16)
    b = imagen[:, :, 2].astype(np.int16)
    azul = ((r + g + b) < 3 * 150) & (b - r > 25)
    return sorted(_componentes(azul), key=lambda c: (c[1], c[0]))[:MAX_BOTONES]


def _leer_boton(imagen: np.ndarray, caja: tuple[int, int, int, int], lang: str) -> str:
    """Lee el texto de un botón recortado (Tesseract lo lee bien aislado, no en la página)."""
    x, y, w, h = caja
    recorte = Image.fromarray(imagen[max(y - 3, 0):y + h + 3, max(x - 3, 0):x + w + 3])
    recorte = recorte.resize((recorte.width * 3, recorte.height * 3), Image.LANCZOS)
    for psm in (8, 13):
        t = pytesseract.image_to_string(recorte, lang=lang, config=f"--psm {psm}")
        t = _limpiar_boton(t)
        if len(t) >= 2 and any(c.isalpha() for c in t):
            return t
    return ""


def _limpiar_boton(t: str) -> str:
    """Quita los signos sueltos que Tesseract pega en los bordes del botón (|, ”, ", ] ...)."""
    palabras = [re.sub(r"^[\W_]+|[\W_]+$", "", w) for w in t.split()]
    return " ".join(w for w in palabras if w)


def leer_textos(imagen: np.ndarray, lang: str, escala: float = 2.0, botones: bool = True) -> list[Elemento]:
    """Tesseract sobre la captura. Numera de arriba hacia abajo y de izquierda a derecha.

    - Se amplía la captura antes de leer (medido: a 2x acierta más textos que a 1x); las
      posiciones se devuelven en píxeles de la pantalla real.
    - Los botones azules (Guardar, Buscar) tienen texto blanco que Tesseract no encuentra al
      leer la página entera (medido), pero sí al leerlos recortados: se detectan por color y
      se leen uno por uno. El botón reemplaza lo que la lectura general viera dentro de él.
    """
    img = Image.fromarray(imagen)
    if escala != 1:
        img = img.resize((int(img.width * escala), int(img.height * escala)), Image.LANCZOS)
    frases = _ocr(img, lang, escala)
    if botones:
        for caja in _rectangulos_oscuros(imagen):
            texto = _leer_boton(imagen, caja, lang)
            if not texto:
                continue
            frases = [f for f in frases if not _contenida(f, caja)]
            frases.append((texto, *caja))
    # Filas: agrupa por franja vertical de ~10 px para que "arriba a abajo" no dependa de 1-2 px.
    frases.sort(key=lambda f: (round(f[2] / 10), f[1]))
    return [Elemento(n=i + 1, texto=t, x=x, y=y, w=w, h=h) for i, (t, x, y, w, h) in enumerate(frases)]


def _normalizar(t: str) -> str:
    sin_tildes = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", sin_tildes.lower()).strip()


def _cajas_de_boton_en_zona(zona: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Manchas lisas del tamaño de un botón dentro de la zona (cara del botón, separada del
    fondo por su borde). Se prueban los colores más frecuentes de la zona, uno por uno, con
    tolerancia suficiente para caras con degradado."""
    cuantizado = (zona // 8).reshape(-1, 3).astype(np.int32)  # int32: evita desbordar uint8
    claves = cuantizado[:, 0] * 1024 + cuantizado[:, 1] * 32 + cuantizado[:, 2]
    valores, cuentas = np.unique(claves, return_counts=True)
    cajas: set[tuple[int, int, int, int]] = set()
    for idx in np.argsort(cuentas)[::-1][:12]:
        if cuentas[idx] < 120:
            break
        v = int(valores[idx])
        color = np.array([(v // 1024) * 8 + 4, ((v // 32) % 32) * 8 + 4, (v % 32) * 8 + 4])
        mascara = np.all(np.abs(zona.astype(np.int16) - color) <= 14, axis=2)
        cajas.update(_componentes(mascara, min_alto=16))
    r, g, b = (zona[:, :, i].astype(np.int16) for i in range(3))
    cajas.update(_componentes(((r + g + b) < 3 * 150) & (b - r > 25), min_alto=16))  # botones azules
    return sorted(cajas)


def ubicar_texto_en_zona(
    imagen: np.ndarray, texto: str, x: int, y: int, lang: str,
    mitad_ancho: int = 200, mitad_alto: int = 60,
) -> tuple[int, int, int, int] | None:
    """Busca el botón `texto` cerca de (x, y) y devuelve su caja exacta (x, y, w, h).

    Sirve para botones que la lectura de toda la pantalla no encuentra: la IA (que ve la
    captura) dice "está más o menos aquí"; el código busca dentro de esa zona las manchas
    del tamaño de un botón y lee, recortadas, las más cercanas (un recorte ajustado sí se lee).
    """
    alto, ancho = imagen.shape[:2]
    x0, y0 = max(0, x - mitad_ancho), max(0, y - mitad_alto)
    x1, y1 = min(ancho, x + mitad_ancho), min(alto, y + mitad_alto)
    if x1 - x0 < 30 or y1 - y0 < 20:
        return None
    objetivo = _normalizar(texto)
    if not objetivo:
        return None
    zona = imagen[y0:y1, x0:x1]
    candidatas = [(bx + x0, by + y0, bw, bh) for bx, by, bw, bh in _cajas_de_boton_en_zona(zona)]
    candidatas.sort(key=lambda c: abs(c[0] + c[2] / 2 - x) + abs(c[1] + c[3] / 2 - y))
    for caja in candidatas[:6]:
        leido = _leer_boton(imagen, caja, lang)
        n = _normalizar(leido)
        if n and (SequenceMatcher(None, n, objetivo).ratio() >= 0.8 or objetivo in n.split()):
            return caja
    return None


async def mirar(
    vnc: Vnc, cfg: Config, antes: np.ndarray | None = None, exigir_cambio: bool = False
) -> Vista:
    """Capturar hasta que esté quieta y leer los textos (Tesseract va en otro hilo)."""
    imagen, quieta, cambio, espera = await capturar_quieta(vnc, cfg, antes, exigir_cambio)
    t0 = time.perf_counter()
    elementos = await asyncio.to_thread(
        leer_textos, imagen, cfg.ocr_lang, cfg.ocr_scale, cfg.ocr_botones)
    return Vista(imagen=imagen, elementos=elementos, quieta=quieta, cambio=cambio,
                 espera_s=espera, ocr_s=time.perf_counter() - t0)


def a_png(imagen: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(imagen).save(buf, format="PNG", optimize=False)
    return buf.getvalue()
