"""Banco de pruebas: por cada archivo de pruebas/ -> reset -> agente -> /__check -> revisar.

Uso:
    .venv/bin/python bench.py                              # arranca el servicio local y corre todo
    .venv/bin/python bench.py --casos E1                   # solo E1
    .venv/bin/python bench.py --modelo qwen/qwen3.8-flash  # compara modelos (servicio local)
    .venv/bin/python bench.py --base https://frontier.jutilabs.com   # contra el publicado

Con --base se usa ese servicio tal cual (el modelo lo fija su .env, --modelo no aplica).
Lee del .env: TEAM_TOKEN, DESKTOP_URL, DESKTOP_PASSWORD, DESKTOP_TOKEN. Nunca imprime secretos.
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from app.config import cargar_env  # noqa: E402
from app.secretos import ocultar  # noqa: E402

_NUM = re.compile(r"-?\d[\d.,]*")


def base_http(ws_url: str) -> str:
    u = urlparse(ws_url)
    return ("https" if u.scheme == "wss" else "http") + "://" + u.netloc


def primer_numero(texto: str) -> str | None:
    m = _NUM.search(texto)
    return m.group(0).replace(".", "").replace(",", "") if m else None


def evaluar_resumen(caso: dict, estado: str, resumen: str, secretos: list[str]) -> list[str]:
    """Devuelve la lista de problemas (vacía = el estado y el resumen están bien)."""
    problemas = []
    if estado != caso["estado_esperado"]:
        problemas.append(f"estado {estado!r}, se esperaba {caso['estado_esperado']!r}")
    linea = re.search(r"^\s*respuesta\s*:\s*(.*)$", resumen, re.I | re.M)
    if "respuesta_esperada" in caso:
        if not linea:
            problemas.append("falta la línea 'respuesta:'")
        else:
            esperado = str(caso["respuesta_esperada"])
            obtenido = primer_numero(linea.group(1)) if primer_numero(esperado) else linea.group(1).strip()
            if obtenido != (primer_numero(esperado) or esperado):
                problemas.append(f"respuesta {obtenido!r}, se esperaba {esperado!r}")
    for clave in caso.get("claves_razon", []):
        if clave not in resumen:
            problemas.append(f"el resumen no nombra {clave!r}")
    if any(s and len(s) >= 3 and s in resumen for s in secretos):
        problemas.append("el resumen contiene un secreto")
    return problemas


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def arrancar_local(modelo: str | None) -> tuple[subprocess.Popen, str]:
    puerto = puerto_libre()
    env = dict(os.environ)
    if modelo:
        env["LLM_MODEL"] = modelo
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:crear_app", "--factory",
         "--host", "127.0.0.1", "--port", str(puerto), "--log-level", "warning"],
        cwd=RAIZ, env=env,
    )
    base = f"http://127.0.0.1:{puerto}"
    token = os.environ["TEAM_TOKEN"]
    for _ in range(40):
        try:
            r = httpx.get(f"{base}/health", headers={"Authorization": f"Bearer {token}"}, timeout=2)
            if r.status_code == 200:
                return proc, base
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    proc.terminate()
    raise SystemExit("El servicio local no arrancó.")


def correr_caso(caso: dict, base: str, tope_s: float, secretos: list[str]) -> dict:
    team = {"Authorization": f"Bearer {os.environ['TEAM_TOKEN']}"}
    esc_url = os.environ["DESKTOP_URL"]
    esc = base_http(esc_url)
    desk = {"Authorization": f"Bearer {os.environ['DESKTOP_TOKEN']}"}
    fila = {"id": caso["id"], "estado": "?", "resumen": "", "check": None, "problemas": [],
            "segundos": 0.0, "costo": None, "pasos": None, "post_s": None}
    paso = "reset"
    try:
        r = httpx.post(f"{esc}/__reset", headers=desk, timeout=90)
        if r.status_code >= 300:
            fila["problemas"].append(f"reset falló ({r.status_code})")
            return fila
        time.sleep(2)

        paso = "POST /tasks"
        cuerpo = {"tarea": caso["instruccion"],
                  "escritorio": {"url": esc_url, "password": os.environ["DESKTOP_PASSWORD"]}}
        t0 = time.perf_counter()
        r = httpx.post(f"{base}/tasks", headers=team, json=cuerpo, timeout=20)
        fila["post_s"] = time.perf_counter() - t0
        if r.status_code != 200:
            fila["problemas"].append(f"POST /tasks respondió {r.status_code}")
            return fila
        task_id = r.json()["task_id"]
        if fila["post_s"] >= 2:
            fila["problemas"].append(f"POST /tasks tardó {fila['post_s']:.1f} s (máximo 2 s)")

        paso = "GET /tasks/{id}"
        estado, resumen, fallos = "en_curso", "", 0
        while time.perf_counter() - t0 < tope_s:
            time.sleep(3)
            try:
                t_poll = time.perf_counter()
                g = httpx.get(f"{base}/tasks/{task_id}", headers=team, timeout=15).json()
                fila.setdefault("consultas_ms", []).append((time.perf_counter() - t_poll) * 1000)
            except httpx.HTTPError as e:  # un corte aislado no tumba la prueba
                fallos += 1
                fila["problemas"].append(f"consulta {fallos} falló: {type(e).__name__}")
                if fallos >= 5:
                    break
                continue
            estado, resumen = g["estado"], g["resumen"]
            if estado != "en_curso":
                break
        fila["segundos"] = time.perf_counter() - t0
        if estado == "en_curso":
            fila["problemas"].append(f"sigue en_curso a los {int(tope_s)} s")

        paso = "POST /__check"
        chk = None
        for intento in range(3):  # el escritorio a veces corta la conexión: se reintenta
            try:
                chk = httpx.post(f"{esc}/__check", headers=desk, json=caso, timeout=30)
                break
            except httpx.HTTPError as e:
                fila.setdefault("avisos", []).append(f"/__check intento {intento + 1}: {type(e).__name__}")
                time.sleep(2)
        if chk is None:
            fila["problemas"].append("/__check no respondió en 3 intentos")
            return fila
        fila["check"] = chk.json() if chk.status_code == 200 else {"pass": False, "checks": []}
        if not fila["check"].get("pass"):
            malos = [c["nombre"] for c in fila["check"].get("checks", []) if not c.get("ok")]
            motivo = ", ".join(malos) or f"/__check {chk.status_code}"
            fila["problemas"].append("la app no quedó bien: " + motivo)

        fila["problemas"] += evaluar_resumen(caso, estado, resumen, secretos)
        fila["estado"], fila["resumen"] = estado, ocultar(resumen, secretos)

        paso = "GET /tasks/{id}/detalle"
        d = httpx.get(f"{base}/tasks/{task_id}/detalle", headers=team, timeout=15)
        if d.status_code == 200:
            det = d.json()
            fila["costo"], fila["pasos"] = det.get("costo_usd"), det.get("pasos")
            fila["tiempos"] = {k: det.get(k) for k in
                               ("seg_espera_pantalla", "seg_leer_textos", "seg_ia", "seg_acciones")}
    except httpx.HTTPError as e:
        fila["problemas"].append(f"error de red en «{paso}»: {type(e).__name__}")
    return fila


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base", help="URL del servicio ya publicado (si falta, arranca uno local)")
    ap.add_argument("--modelo", help="modelo de OpenRouter para el servicio local")
    ap.add_argument("--casos", help="ids separados por coma (por defecto, todos)")
    ap.add_argument("--tope", type=float, default=300, help="segundos máximos por caso")
    a = ap.parse_args()

    cargar_env()
    for k in ("TEAM_TOKEN", "DESKTOP_URL", "DESKTOP_PASSWORD", "DESKTOP_TOKEN"):
        if not os.environ.get(k):
            raise SystemExit(f"Falta {k} en .env")
    secretos = [os.environ[k] for k in ("DESKTOP_PASSWORD", "DESKTOP_TOKEN", "TEAM_TOKEN")]

    casos = [json.loads(p.read_text()) for p in sorted((RAIZ / "pruebas").glob("*.json"))]
    if a.casos:
        quiero = {c.strip().upper() for c in a.casos.split(",")}
        casos = [c for c in casos if c["id"].upper() in quiero]
    if not casos:
        raise SystemExit("No hay casos que correr.")

    proc = None
    if a.base:
        base = a.base.rstrip("/")
        modelo = "(el del servicio publicado)"
        if a.modelo:
            print("Aviso: --modelo no aplica con --base; el servicio usa el suyo.")
    else:
        proc, base = arrancar_local(a.modelo)
        modelo = a.modelo or os.environ.get("LLM_MODEL", "(por defecto)")

    print(f"Servicio: {base}   Modelo: {modelo}   Casos: {', '.join(c['id'] for c in casos)}\n")
    filas = []
    try:
        for c in casos:
            print(f"-> {c['id']} {c['instruccion'][:70]}", flush=True)
            f = correr_caso(c, base, a.tope, secretos)
            filas.append(f)
            print(f"   {'PASÓ' if not f['problemas'] else 'FALLÓ'} en {f['segundos']:.0f} s", flush=True)
    finally:
        if proc:
            proc.terminate()

    print("\n  caso   pasó   estado     tiempo   costo US$   pasos")
    for f in filas:
        costo = f"{f['costo']:.4f}" if f["costo"] is not None else "  -  "
        pasos = f["pasos"] if f["pasos"] is not None else "-"
        print(f"  {f['id']:<6} {'sí ' if not f['problemas'] else 'NO '}    {f['estado']:<10} "
              f"{f['segundos']:>5.0f} s   {costo:>9}   {pasos}")
    ok = sum(1 for f in filas if not f["problemas"])
    total = sum(f["costo"] or 0 for f in filas)
    for f in filas:
        c = f.get("consultas_ms")
        if c:
            c = sorted(c)
            print(f"\n  [{f['id']}] GET /tasks/{{id}}: {len(c)} consultas · mediana {c[len(c) // 2]:.0f} ms"
                  f" · más lenta {c[-1]:.0f} ms · POST /tasks {f['post_s'] * 1000:.0f} ms")
    if any(f.get("tiempos") and f["tiempos"].get("seg_ia") is not None for f in filas):
        print("\n  Dónde se va el tiempo (segundos, por caso)")
        print("  caso   total   pantalla   textos     IA    acciones   otros   s/paso")
        for f in filas:
            t = f.get("tiempos")
            if not t or t.get("seg_ia") is None:
                continue
            suma = sum(t.values())
            otros = f["segundos"] - suma
            por_paso = f["segundos"] / f["pasos"] if f["pasos"] else 0
            print(f"  {f['id']:<6} {f['segundos']:>5.0f}   {t['seg_espera_pantalla']:>7.0f}   "
                  f"{t['seg_leer_textos']:>6.0f}   {t['seg_ia']:>5.0f}   {t['seg_acciones']:>7.0f}   "
                  f"{otros:>5.0f}   {por_paso:>6.1f}")
    print(f"\n  {ok}/{len(filas)} pasaron · costo total US${total:.4f} · modelo {modelo}")
    for f in filas:
        if f["problemas"]:
            print(f"\n  [{f['id']}] problemas: " + " | ".join(f["problemas"]))
            print(f"  [{f['id']}] resumen del agente: {f['resumen'][:400]!r}")
    sys.exit(0 if ok == len(filas) else 1)


if __name__ == "__main__":
    main()
