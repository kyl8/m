from __future__ import annotations

import argparse
import json
import random
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from config import get_settings
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from consumer.parser import parse_uplink
from consumer.state_store import StateStore
from mqtt.publisher import MqttPublisher
from project_io import iso_now, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def send_manifest(messages: int, devices: int) -> Path:
    settings = get_settings()
    publisher = MqttPublisher(settings, "network-pipeline-sender")
    rng = random.Random()
    states = {f"sonda-network-{number:03d}": SensorState.create(rng) for number in range(1, devices + 1)}
    state = StateStore(settings.state_db)
    records = []
    started_at = iso_now()
    try:
        publisher.connect()
        for index in range(messages):
            device_id = f"sonda-network-{index % devices + 1:03d}"
            frame = state.next_simulator_frame(device_id)
            payload = make_uplink(
                device_id, frame, states[device_id].next_reading(rng), simulated_radio(100, rng),
                site="network-test",
            )
            publisher.publish(payload)
            records.append({"reading": parse_uplink(payload), "published_at": iso_now()})
    finally:
        publisher.close()
    evidence = {
        "test": "NETWORK DATA PIPELINE TEST - SEND",
        "started_at": started_at,
        "finished_at": iso_now(),
        "status": "PASS" if len(records) == messages else "FAIL",
        "radio_mode": "SIMULATED",
        "physical_range_validation": "NOT PERFORMED",
        "simulator_host": _host_info(),
        "mqtt_host": _resolve(settings.mqtt_host, settings.mqtt_port),
        "expected": {"messages": messages},
        "actual": {"published": len(records)},
        "messages": records,
    }
    path = save_artifact("evidence", "network_send_manifest", evidence)
    print(f"[PASS] {len(records)} messages published through MQTT")
    print(f"Manifest: {path}")
    print("Copy this manifest to the consumer host and run network_pipeline.py verify --manifest PATH")
    return path


def verify_manifest(path: Path) -> dict[str, Any]:
    settings = get_settings()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    state = StateStore(settings.state_db)
    writer = InfluxWriter(settings)
    found = received = exact = 0
    traces = []
    status = "NOT EXECUTED"
    error = None
    try:
        version = writer.connect()
        for entry in manifest["messages"]:
            reading = entry["reading"]
            local = state.get_message(reading["message_id"])
            if local:
                received += 1
            ok, stored, differences = writer.verify(reading)
            if stored:
                found += 1
            if ok:
                exact += 1
            traces.append({
                "message_id": reading["message_id"],
                "sent_at": reading["sent_at"],
                "published_at": entry["published_at"],
                "consumer_received_at": local.get("received_at") if local else None,
                "database_confirmed_at": iso_now() if ok else None,
                "differences": differences,
            })
        expected = len(manifest["messages"])
        status = "PASS" if received == found == exact == expected else "FAIL"
    except InfluxUnavailable as exc:
        version = None
        error = str(exc)
    finally:
        writer.close()
    expected = len(manifest["messages"])
    report = {
        "test": "NETWORK DATA PIPELINE TEST - VERIFY",
        "started_at": manifest["started_at"],
        "finished_at": iso_now(),
        "status": status,
        "simulator_host": manifest["simulator_host"],
        "mqtt_host": manifest["mqtt_host"],
        "consumer_host": _host_info(),
        "influx_host": _resolve(urlparse(settings.influx_url).hostname or "unknown", urlparse(settings.influx_url).port or 8086),
        "influx_version": version,
        "expected": {"messages": expected},
        "actual": {"received": received, "found": found, "exact_match": exact, "loss": expected - exact},
        "error": error,
        "traces": traces,
        "conclusion": "REAL TCP/IP NETWORK COMMUNICATION; NOT A LORAWAN RANGE TEST",
    }
    evidence = save_artifact("evidence", "network_verify", report)
    reports = save_report("network_pipeline", report)
    print(f"Received: {received}/{expected}")
    print(f"Found and exact: {exact}/{expected}")
    print(f"RESULT: {status}")
    print(f"Evidence: {evidence}")
    print(f"Reports: {reports[0]}, {reports[1]}")
    return report


def _host_info() -> dict[str, str]:
    name = socket.gethostname()
    return {"hostname": name, "ip": _ip(name)}


def _resolve(host: str, port: int) -> dict[str, Any]:
    return {"hostname": host, "ip": _ip(host), "port": port}


def _ip(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return "UNRESOLVED"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prova de comunicação TCP/IP entre máquinas")
    sub = parser.add_subparsers(dest="command", required=True)
    send = sub.add_parser("send")
    send.add_argument("--messages", type=int, default=100)
    send.add_argument("--devices", type=int, default=10)
    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "send":
        send_manifest(args.messages, args.devices)
    else:
        verify_manifest(args.manifest)
