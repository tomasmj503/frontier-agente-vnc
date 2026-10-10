#!/usr/bin/env python3
"""Corre casos de prueba contra una o más URLs y compara código HTTP y cuerpo.

Uso:
    python3 -I run_cases.py CASOS.jsonl --base http://localhost:8000 \
        --base https://url-publica.example.com --max-seconds <límite del BRIEF.md>

--max-seconds: un caso que tarde más se marca FAIL. Cada petición espera como
máximo --max-seconds + 5 s; si no se pasa, espera hasta 120 s y no mide tiempo.

Cada línea de CASOS.jsonl es un objeto JSON con:
    id           nombre del caso (el mismo de DISENO.md)
    method       "GET" o "POST" (por defecto GET)
    path         ruta, por ejemplo "/health"
    headers      objeto opcional; el valor "$TOKEN" se reemplaza por la
                 variable de entorno EVAL_TOKEN (el token nunca se imprime)
    body         objeto JSON a enviar (opcional)
    raw_body     texto a enviar tal cual, para probar JSON roto (opcional)
    expect_http  código HTTP esperado (200, 400, 401...)
    expect_body  cuerpo esperado (opcional; si falta, el cuerpo no se compara):
                 cada clave indicada debe existir con ese valor y el cuerpo
                 real puede traer campos extra. Excepción: un objeto vacío {}
                 (en cualquier nivel) exige un {} exacto, sin datos dentro.

Sale con código 1 si algún caso falla, 2 si faltan datos para correr.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_WAIT_S = 120  # espera máxima por petición si no se pasa --max-seconds
GRACE_S = 5           # margen sobre --max-seconds para poder medir cuánto tardó de verdad


def wait_limit(max_seconds):
    """Cuánto espera cada petición antes de rendirse."""
    return DEFAULT_WAIT_S if max_seconds is None else max_seconds + GRACE_S


def contains(expected, actual):
    """True si todo lo esperado aparece en lo recibido (objetos: por clave).

    Un objeto vacío esperado ({}) exige que lo recibido sea exactamente {}.
    """
    if isinstance(expected, dict):
        if not expected:
            return actual == {}
        return isinstance(actual, dict) and all(
            key in actual and contains(value, actual[key]) for key, value in expected.items()
        )
    return expected == actual


def short(value, limit=400):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + "…"


def call(base, case, token, timeout):
    """Hace la petición. Devuelve (código_http | None, cuerpo, segundos)."""
    headers = {
        name: (token if value == "$TOKEN" else value)
        for name, value in case.get("headers", {}).items()
    }
    data = None
    if "raw_body" in case:
        data = case["raw_body"].encode("utf-8")
    elif "body" in case:
        data = json.dumps(case["body"]).encode("utf-8")
    if data is not None:
        headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        base.rstrip("/") + case["path"],
        data=data,
        headers=headers,
        method=case.get("method", "GET"),
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code, raw = response.status, response.read()
    except urllib.error.HTTPError as error:  # 4xx y 5xx también son respuestas válidas
        code, raw = error.code, error.read()
    except Exception as error:  # sin red, DNS, timeout
        return None, f"<sin respuesta: {type(error).__name__}>", time.perf_counter() - started
    elapsed = time.perf_counter() - started

    text = raw.decode("utf-8", errors="replace")
    try:
        return code, json.loads(text), elapsed
    except ValueError:
        return code, text, elapsed


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("cases", help="archivo .jsonl con los casos")
    parser.add_argument("--base", action="append", required=True, help="URL base; se puede repetir")
    parser.add_argument("--max-seconds", type=float, default=None, help="falla si un caso tarda más")
    args = parser.parse_args()

    with open(args.cases, encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    if not cases:
        print("El archivo de casos está vacío.", file=sys.stderr)
        return 2

    token = os.environ.get("EVAL_TOKEN")
    needs_token = any("$TOKEN" in case.get("headers", {}).values() for case in cases)
    if needs_token and not token:
        print("Falta la variable de entorno EVAL_TOKEN (token válido de pruebas).", file=sys.stderr)
        return 2

    timeout = wait_limit(args.max_seconds)
    any_failure = False
    for base in args.base:
        print(f"\n=== {base} ===")
        passed = 0
        for case in cases:
            code, body, seconds = call(base, case, token, timeout)
            has_expected_body = "expect_body" in case
            expected_body = case.get("expect_body")

            reasons = []
            if code != case["expect_http"]:
                reasons.append("código HTTP distinto")
            if has_expected_body and not contains(expected_body, body):
                reasons.append("cuerpo distinto")
            if args.max_seconds is not None and seconds > args.max_seconds:
                reasons.append(f"tardó más de {args.max_seconds:g} s")

            verdict = "FAIL" if reasons else "PASS"
            passed += not reasons
            print(
                f"{case['id']:<6} {verdict}  HTTP {code} (esperado {case['expect_http']})"
                f"  {seconds:.2f}s" + (f"  <- {', '.join(reasons)}" if reasons else "")
            )
            print(f"       recibido: {short(body)}")
            print(f"       esperado: {short(expected_body) if has_expected_body else '(sin cuerpo esperado)'}")

        print(f"--- {base}: {passed}/{len(cases)} casos correctos")
        any_failure = any_failure or passed != len(cases)

    return 1 if any_failure else 0


if __name__ == "__main__":
    sys.exit(main())
