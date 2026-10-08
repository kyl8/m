from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.status import build_status, console, environment_status
from config import ROOT, get_settings
from consumer.consumer import Consumer
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from consumer.state_store import StateStore
from mqtt.mqtt_check import run_mqtt_check
from mqtt.publisher import MqttPublisher
from project_io import iso_now, parse_time, save_artifact, save_report
from simulator.simulator import run_simulation
from tests.integration.test_end_to_end import run_end_to_end
from tests.integration.test_failures import (
    run_influx_outage_and_optional_recovery,
    run_mqtt_unavailable_detection,
)
from tests.integration.test_influx import perform_influx_test
from tests.load.load_test import run_load


def heading(title: str, explanation: str) -> None:
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)
    print(explanation.strip() + "\n")


def check_environment() -> None:
    heading(
        "VERIFICAÇÃO DO AMBIENTE",
        "Verificamos configuração e acesso de rede. Este passo não grava dados.",
    )
    status = environment_status()
    _line("PYTHON", True, sys.version.split()[0])
    _line("MQTT CONFIG", status["mqtt_configured"], status["mqtt_target"])
    _line("MQTT CONNECTION", status["mqtt_online"], status["mqtt_target"])
    _line("INFLUX CONFIG", status["influx_configured"], status["influx_target"])
    _line("INFLUX CONNECTION", status["influx_online"], status.get("influx_error"))
    print(f"InfluxDB detected version: {status['influx_version'] or 'NOT DETECTED'}")


def validate_requirements() -> None:
    heading(
        "VALIDAÇÃO DOS REQUISITOS",
        "Além de conectar, escrevemos e consultamos dados reais nos dois serviços.",
    )
    env = environment_status()
    _line("PYTHON", True)
    _line("MQTT CONFIG", env["mqtt_configured"])
    mqtt = run_mqtt_check(verbose=False) if env["mqtt_online"] else {"status": "NOT EXECUTED"}
    _line("MQTT CONNECTION", mqtt["status"] == "PASS", mqtt["status"])
    _line("INFLUX CONFIG", env["influx_configured"])
    influx = perform_influx_test(verbose=False) if env["influx_configured"] else {"status": "NOT EXECUTED"}
    ok = influx["status"] == "PASS"
    _line("INFLUX CONNECTION", ok, influx["status"])
    _line("INFLUX AUTH", ok, influx.get("error"))
    _line("TARGET DATABASE/BUCKET", ok, get_settings().influx_bucket or "not configured")
    _line("WRITE TEST", ok)
    _line("QUERY TEST", ok)
    ready = mqtt["status"] == "PASS" and ok
    _line("SYSTEM READY", ready)


def invalid_message_test() -> None:
    heading(
        "TESTE DE MENSAGEM INVÁLIDA",
        "Publicamos pH como texto. O consumer deve receber e rejeitar por formato.",
    )
    settings = get_settings()
    consumer = Consumer(settings)
    publisher = MqttPublisher(settings, "invalid-test")
    before = consumer.state.counters().get("rejected", 0)
    message_id = str(uuid4())
    payload = {
        "end_device_ids": {"device_id": "sonda-invalid-test"},
        "received_at": iso_now(),
        "uplink_message": {
            "f_cnt": 1,
            "decoded_payload": {
                "message_id": message_id,
                "sent_at": iso_now(),
                "source": "simulator",
                "ph": "abc",
            },
            "rx_metadata": [],
        },
    }
    result = "FAIL"
    error = None
    try:
        consumer.start()
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não conectou")
        publisher.connect()
        publisher.publish(payload)
        deadline = time.monotonic() + settings.mqtt_timeout
        while time.monotonic() < deadline:
            if consumer.state.counters().get("rejected", 0) > before:
                result = "PASS"
                break
            time.sleep(0.1)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        error = str(exc)
    finally:
        publisher.close()
        consumer.stop()
    evidence = save_artifact("evidence", "invalid_message", {
        "test": "INVALID MESSAGE", "started_at": payload["received_at"], "finished_at": iso_now(),
        "status": result, "expected": {"rejected": True}, "actual": {"rejected": result == "PASS"}, "error": error,
    })
    save_report("invalid_message", {
        "test": "INVALID MESSAGE", "status": result, "message_id": message_id,
        "expected": {"rejected": True}, "actual": {"rejected": result == "PASS"}, "error": error,
    })
    print(f"RESULT: {result}")
    if error:
        print(f"Reason: {error}")
    print(f"Evidence: {evidence}")


def pollution_demo() -> None:
    heading(
        "EVENTO AMBIENTAL SIMULADO",
        "A turbidez da sonda-003 aumenta gradualmente. O alerta demonstra detecção de mudança e não confirma poluição real.",
    )
    settings = get_settings()
    consumer = Consumer(settings)
    baseline = consumer.state.counters()
    started_at = iso_now()
    try:
        consumer.start()
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não conectou ao MQTT")
        simulation = run_simulation(3, 60, "stress", 0.02, "pollution", 0, 100, False)
        deadline = time.monotonic() + settings.mqtt_timeout
        while time.monotonic() < deadline:
            counters = consumer.state.counters()
            if counters.get("received", 0) - baseline.get("received", 0) >= 60:
                break
            time.sleep(0.1)
    finally:
        consumer.stop()
    counters = consumer.state.counters()
    actual = {
        "published": simulation.get("published", 0),
        "received": counters.get("received", 0) - baseline.get("received", 0),
        "environmental_events": counters.get("environmental_events", 0) - baseline.get("environmental_events", 0),
    }
    status = "PASS" if actual["published"] == actual["received"] == 60 and actual["environmental_events"] >= 1 else "FAIL"
    result = {
        "test": "SIMULATED ENVIRONMENTAL EVENT", "started_at": started_at, "finished_at": iso_now(),
        "status": status, "expected": {"published": 60, "received": 60, "environmental_events_min": 1},
        "actual": actual, "radio_mode": "SIMULATED", "physical_range_validation": "NOT PERFORMED",
    }
    evidence = save_artifact("evidence", "pollution_event", result)
    save_report("pollution_event", result)
    print(f"RESULT: {status}")
    print(f"Evidence: {evidence}")


def failure_test() -> None:
    heading(
        "TESTE DE RECUPERAÇÃO DE FALHA",
        "Usamos uma URL InfluxDB indisponível, comprovamos a fila SQLite e, se o banco real estiver configurado, confirmamos a recuperação por consulta.",
    )
    influx = run_influx_outage_and_optional_recovery()
    mqtt = run_mqtt_unavailable_detection()
    print(f"InfluxDB offline queue......... {influx['actual']['queued_while_offline']}")
    print(f"InfluxDB recovery.............. {influx['actual']['recovery']}")
    print(f"MQTT offline detection......... {mqtt['status']}")
    print("MQTT restart and reconnect..... NOT TESTED (requires controlled broker restart)")
    print(f"Evidence: {influx['evidence']}")
    print(f"Evidence: {mqtt['evidence']}")


def trace_message() -> None:
    message_id = input("Message ID: ").strip()
    settings = get_settings()
    state = StateStore(settings.state_db)
    trace = state.get_message(message_id)
    heading("MESSAGE TRACE", "Cada horário abaixo foi registrado durante uma operação real.")
    if not trace:
        print("[FAIL] Message ID not found in local trace database.")
        return
    original = json.loads(trace.get("original_json") or "{}")
    stored = None
    query_error = None
    if settings.influx_configured:
        writer = InfluxWriter(settings)
        try:
            stored = writer.query_message(message_id)
        except InfluxUnavailable as exc:
            query_error = str(exc)
        finally:
            writer.close()
    query_at = iso_now() if stored else None
    if query_at and not trace.get("confirmed_at"):
        state.stage(message_id, "confirmed", occurred_at=query_at)
        trace = state.get_message(message_id) or trace
    print(f"Message ID: {message_id}")
    print(f"Device: {trace.get('device_id')}\n")
    for key, label in (
        ("generated_at", "GENERATED"), ("published_at", "MQTT PUBLISHED"),
        ("received_at", "CONSUMER RECEIVED"), ("validated_at", "VALIDATED"),
        ("written_at", "INFLUXDB WRITE"),
    ):
        _trace_line(label, trace.get(key))
    _trace_line("DATABASE CONFIRMED", trace.get("confirmed_at"))
    _trace_line("TRACE QUERY NOW / RECORD FOUND", query_at)
    print("\nOriginal:")
    print(f"temperature_c = {original.get('temperature_c')}")
    print(f"ph = {original.get('ph')}")
    print("Stored:")
    print(f"temperature_c = {stored.get('temperature_c') if stored else None}")
    print(f"ph = {stored.get('ph') if stored else None}")
    if trace.get("generated_at") and trace.get("confirmed_at"):
        total = (
            parse_time(trace["confirmed_at"]) - parse_time(trace["generated_at"])
        ).total_seconds() * 1000
        print(f"\nTOTAL LATENCY: {total:.2f} ms")
    stages = all(trace.get(key) for key in (
        "generated_at", "published_at", "received_at", "validated_at", "written_at"
    ))
    exact = stages and stored is not None and all(
        stored.get(key) == original.get(key) for key in ("temperature_c", "ph")
    )
    print(f"FINAL RESULT: {'PASS' if exact else 'FAIL'}")
    if query_error:
        print(f"Query error: {query_error}")


def show_recent() -> None:
    state = StateStore(get_settings().state_db)
    rows = state.recent(10)
    if not rows:
        print("Nenhuma mensagem registrada localmente.")
        return
    for row in rows:
        print(f"{row['received_at']} | {row['device_id']} | {row['message_id']} | {row['status']}")


def show_doc(filename: str) -> None:
    path = ROOT / "docs" / filename
    print(path.read_text(encoding="utf-8") if path.exists() else f"Documento ainda não encontrado: {path}")


def _line(label: str, passed: bool, detail: object = None) -> None:
    status = "PASS" if passed else (str(detail) if detail in {"NOT EXECUTED", "SKIPPED"} else "FAIL")
    suffix = "" if detail is None or detail == status else f"  ({detail})"
    print(f"{label:.<30} {status}{suffix}")


def _trace_line(label: str, timestamp: str | None) -> None:
    print(f"{label:<30} {timestamp or 'NO'} {'PASS' if timestamp else 'FAIL'}")


def pause() -> None:
    input("\nPressione ENTER para continuar.")


def menu() -> None:
    actions: dict[str, Callable[[], None]] = {
        "1": check_environment,
        "2": lambda: run_mqtt_check(),
        "3": lambda: perform_influx_test(),
        "4": lambda: run_end_to_end(100, 1),
        "5": lambda: run_end_to_end(100, 10),
        "6": lambda: run_end_to_end(1000, 100),
        "7": _large_volume,
        "8": pollution_demo,
        "9": invalid_message_test,
        "10": failure_test,
        "11": show_recent,
        "12": lambda: console.print(build_status()[0]),
        "13": lambda: show_doc("arquitetura.md"),
        "14": lambda: show_doc("requisitos_dados.md"),
        "15": trace_message,
        "16": validate_requirements,
    }
    while True:
        print("""
============================================================
 PORTOS CONECTADOS - DEMONSTRAÇÃO
============================================================
[1] Verificar ambiente
[2] Testar MQTT
[3] Testar InfluxDB
[4] Testar fluxo completo (100 mensagens)
[5] Simular 10 sondas
[6] Simular 100 sondas
[7] Teste de grande volume
[8] Simular evento de poluição
[9] Testar mensagem inválida
[10] Testar recuperação de falha
[11] Consultar últimas leituras
[12] Mostrar estatísticas
[13] Ver arquitetura
[14] Mostrar requisitos dos dados
[15] Rastrear uma mensagem
[16] Validar requisitos
[0] Sair
""")
        choice = input("Escolha: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Opção inválida.")
            continue
        try:
            action()
        except (OSError, RuntimeError, TimeoutError, ValueError, KeyError) as exc:
            print(f"[FAIL] {exc}")
        pause()


def _large_volume() -> None:
    value = input("Quantidade (1000, 10000, 50000, 100000 ou 500000): ").strip()
    allowed = {1000, 10_000, 50_000, 100_000, 500_000}
    try:
        messages = int(value)
    except ValueError:
        print("Quantidade inválida.")
        return
    if messages not in allowed:
        print("Use uma das quantidades apresentadas. Os limites protegem a máquina.")
        return
    run_load(min(1000, max(1, messages // 100)), messages)


if __name__ == "__main__":
    menu()
