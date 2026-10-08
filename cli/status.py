from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from config import get_settings
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from consumer.pending_queue import PendingQueue
from consumer.state_store import StateStore
from project_io import latency_stats

console = Console()


def tcp_online(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def environment_status() -> dict[str, Any]:
    settings = get_settings()
    mqtt_online = tcp_online(settings.mqtt_host, settings.mqtt_port)
    influx_online = False
    influx_version = None
    influx_error = None
    if settings.influx_url:
        writer = InfluxWriter(settings)
        try:
            influx_version = writer.detected_version()
            influx_online = True
        except InfluxUnavailable as exc:
            influx_error = str(exc)
    return {
        "mqtt_configured": settings.mqtt_configured,
        "mqtt_online": mqtt_online,
        "mqtt_target": f"{settings.mqtt_host}:{settings.mqtt_port}",
        "influx_configured": settings.influx_configured,
        "influx_online": influx_online,
        "influx_target": settings.influx_url,
        "influx_version": influx_version,
        "influx_error": influx_error,
    }


def build_status(previous: tuple[float, int] | None = None) -> tuple[Panel, tuple[float, int]]:
    settings = get_settings()
    state = StateStore(settings.state_db)
    pending = PendingQueue(settings.pending_db)
    env = environment_status()
    counters = state.counters()
    now = time.monotonic()
    received = counters.get("received", 0)
    rate = 0.0 if previous is None else max(0, received - previous[1]) / max(0.001, now - previous[0])

    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold", width=31)
    table.add_column(justify="right")
    table.add_row("MQTT Broker", _state(env["mqtt_online"]))
    table.add_row("InfluxDB", _state(env["influx_online"]))
    table.add_row("Consumer", _consumer_state(state))
    table.add_row("InfluxDB detected version", str(env["influx_version"] or "NOT DETECTED"))
    table.add_row("", "")
    table.add_row("Mensagens geradas", str(counters.get("generated", 0)))
    table.add_row("MQTT publicadas", str(counters.get("published", 0)))
    table.add_row("Consumer recebeu", str(received))
    table.add_row("Mensagens válidas", str(counters.get("valid", 0)))
    table.add_row("Rejeitadas", str(counters.get("rejected", 0)))
    table.add_row("InfluxDB gravou", str(counters.get("written", 0)))
    table.add_row("Confirmadas por consulta", str(counters.get("confirmed", 0)))
    table.add_row("Duplicadas", str(counters.get("duplicates", 0)))
    table.add_row("Fora de ordem", str(counters.get("out_of_order", 0)))
    table.add_row("Possíveis frames ausentes", str(counters.get("possible_loss", 0)))
    table.add_row("Fila pendente", str(pending.count()))
    table.add_row("Taxa atual", f"{rate:.1f} msg/s")
    latency = latency_stats(state.latencies())
    table.add_row("Latência média", _value(_rounded(latency["average_ms"]), " ms"))
    table.add_row("P95", _value(_rounded(latency["p95_ms"]), " ms"))
    table.add_row("P99", _value(_rounded(latency["p99_ms"]), " ms"))

    recent = state.recent(1)
    if recent:
        item = recent[0]
        try:
            reading = json.loads(item.get("original_json") or "{}")
        except json.JSONDecodeError:
            reading = {}
        table.add_row("", "")
        table.add_row("Última mensagem", str(item.get("message_id")))
        table.add_row("Device", str(item.get("device_id")))
        table.add_row("Temperature", _value(reading.get("temperature_c"), " °C"))
        table.add_row("pH", _value(reading.get("ph")))
        table.add_row("Turbidity", _value(reading.get("turbidity_ntu"), " NTU"))
        table.add_row("Latency", _value(item.get("latency_ms"), " ms"))

    title = "PORTOS CONECTADOS — STATUS DO SISTEMA"
    subtitle = "RADIO MODE: SIMULATED/EXTERNAL | PHYSICAL RANGE VALIDATION: NOT PERFORMED"
    return Panel(table, title=title, subtitle=subtitle), (now, received)


def _state(online: bool) -> str:
    return "[green][ONLINE][/green]" if online else "[red][OFFLINE][/red]"


def _value(value: Any, suffix: str = "") -> str:
    return "-" if value is None else f"{value}{suffix}"


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _consumer_state(state: StateStore) -> str:
    heartbeat = state.get_meta("consumer_heartbeat")
    if state.get_meta("consumer_status") != "RUNNING" or not heartbeat:
        return "[yellow][STOPPED][/yellow]"
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        return "[yellow][UNKNOWN][/yellow]"
    return "[green][RUNNING][/green]" if age <= 15 else "[yellow][STALE][/yellow]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()
    if args.once:
        panel, _ = build_status()
        console.print(panel)
        return
    previous = None
    with Live(console=console, refresh_per_second=4) as live:
        try:
            while True:
                panel, previous = build_status(previous)
                live.update(panel)
                time.sleep(max(0.25, args.interval))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
