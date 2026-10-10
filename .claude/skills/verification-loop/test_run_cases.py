"""Pruebas de run_cases.py.

Correr con:  pytest .claude/skills/verification-loop/ -q
(pytest ignora carpetas que empiezan con punto, así que un `pytest` en la raíz
del proyecto no mezcla estas pruebas con las de la API.)
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import run_cases


# --- contains(): objeto vacío esperado = objeto vacío exacto ---------------

def test_objeto_vacio_esperado_acepta_objeto_vacio():
    assert run_cases.contains({}, {}) is True


def test_objeto_vacio_esperado_rechaza_objeto_con_datos():
    assert run_cases.contains({}, {"valor": 45.17}) is False


@pytest.mark.parametrize("actual", [None, [], "", "texto", 0])
def test_objeto_vacio_esperado_rechaza_lo_que_no_es_objeto(actual):
    assert run_cases.contains({}, actual) is False


def test_objeto_vacio_anidado_exige_vacio_exacto():
    expected = {"status": "not_found", "answer": {}}
    assert run_cases.contains(expected, {"status": "not_found", "answer": {}, "cost_usd": 0})
    assert not run_cases.contains(expected, {"status": "not_found", "answer": {"valor": 1}})


def test_objeto_con_claves_sigue_siendo_subconjunto():
    assert run_cases.contains({"a": 1}, {"a": 1, "b": 2})
    assert not run_cases.contains({"a": 1}, {"b": 2})


# --- main(): sin expect_body no se compara; con {} explícito sí ------------

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow":
            time.sleep(1)  # respuesta lenta, para probar el tiempo de espera
        raw = json.dumps({"status": "ok", "extra": 1}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


@pytest.fixture
def server_url():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run(tmp_path, monkeypatch, capsys, case, url):
    cases = tmp_path / "cases.jsonl"
    cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["run_cases.py", str(cases), "--base", url])
    code = run_cases.main()
    return code, capsys.readouterr().out


def test_sin_expect_body_no_se_compara_el_cuerpo(tmp_path, monkeypatch, capsys, server_url):
    case = {"id": "C1", "path": "/", "expect_http": 200}
    code, out = _run(tmp_path, monkeypatch, capsys, case, server_url)
    assert code == 0
    assert "(sin cuerpo esperado)" in out


def test_expect_body_vacio_explicito_falla_si_llega_contenido(tmp_path, monkeypatch, capsys, server_url):
    case = {"id": "C1", "path": "/", "expect_http": 200, "expect_body": {}}
    code, out = _run(tmp_path, monkeypatch, capsys, case, server_url)
    assert code == 1
    assert "cuerpo distinto" in out


# --- tiempo de espera: --max-seconds + 5, o 120 s si no se pasa -------------

def test_espera_por_defecto_es_120_segundos():
    assert run_cases.wait_limit(None) == 120


@pytest.mark.parametrize("max_seconds, esperado", [(30, 35), (10, 15), (0.5, 5.5)])
def test_espera_es_max_seconds_mas_5(max_seconds, esperado):
    assert run_cases.wait_limit(max_seconds) == esperado


def test_respuesta_lenta_dentro_del_margen_se_recibe_y_marca_fail_por_tiempo(
    tmp_path, monkeypatch, capsys, server_url
):
    # --max-seconds 0.3 → espera 5.3 s: la respuesta de 1 s llega, pero se marca lenta
    case = {"id": "C1", "path": "/slow", "expect_http": 200}
    monkeypatch.setattr(sys, "argv", ["run_cases.py", str(_write(tmp_path, case)),
                                      "--base", server_url, "--max-seconds", "0.3"])
    code = run_cases.main()
    out = capsys.readouterr().out
    assert code == 1
    assert "HTTP 200" in out
    assert "tardó más de 0.3 s" in out


def test_sin_respuesta_dentro_de_la_espera_se_reporta_sin_respuesta(
    tmp_path, monkeypatch, capsys, server_url
):
    # sin margen, --max-seconds 0.3 → espera 0.3 s y la respuesta de 1 s no alcanza a llegar
    monkeypatch.setattr(run_cases, "GRACE_S", 0)
    case = {"id": "C1", "path": "/slow", "expect_http": 200}
    monkeypatch.setattr(sys, "argv", ["run_cases.py", str(_write(tmp_path, case)),
                                      "--base", server_url, "--max-seconds", "0.3"])
    code = run_cases.main()
    out = capsys.readouterr().out
    assert code == 1
    assert "HTTP None" in out
    assert "sin respuesta" in out


def _write(tmp_path, case):
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(case) + "\n", encoding="utf-8")
    return path
