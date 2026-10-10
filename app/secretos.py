"""Filtro de secretos: ningún texto que salga del servicio (IA, resumen, bitácora) los lleva."""
from typing import Iterable

OCULTO = "[oculto]"
_LARGO_MINIMO = 3  # un secreto de 1-2 caracteres dañaría cualquier texto; no se filtra


def ocultar(texto: str, secretos: Iterable[str]) -> str:
    """Reemplaza cada secreto por [oculto]. Primero los más largos, por si uno contiene a otro."""
    limpios = sorted({s for s in secretos if s and len(s) >= _LARGO_MINIMO}, key=len, reverse=True)
    for s in limpios:
        texto = texto.replace(s, OCULTO)
    return texto


def contiene_secreto(texto: str, secretos: Iterable[str]) -> bool:
    return any(s and len(s) >= _LARGO_MINIMO and s in texto for s in secretos)
