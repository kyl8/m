from __future__ import annotations

import os
import random
import time
from typing import Any

import pytest

from config import get_settings
from consumer.consumer import Consumer
from mqtt.publisher import MqttPublisher
from project_io import iso_now, latency_stats, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def run_end_to_end(messages: int = 100, devices: int = 1, rate: float = 0, verbose: bool = True) -> dict[str, Any]:
    settings = get_settings()
    started_at = iso_now()
    result: dict[str, Any] = {
        "test": "END TO END",
        "started_at": started_at,
        "status": "NOT EXECUTED",
        "expected": {"generated": messages, "found_in_influxdb": messages},
        "radio_mode": "SIMULATED",
        "physical_range_validation": "NOT PERFORMED",
    }
    if not settings.influx_configured:
        result["error"] = "InfluxDB não configurado no .env"
        return _finish(result, verbose)

    consumer = Consumer(settings, verify_writes=False, verbose=False)
    publisher = MqttPublisher(settings, client_id="portos-e2e-publisher")
    rng = random.Random()
    sensors = {f"sonda-{i:03d}": SensorState.create(rng) for i in range(1, devices + 1)}
    original: dict[str, dict[str, Any]] = {}
    traces: dict[str, dict[str, Any]] = {}
    generated = published = 0
    baseline = consumer.state.counters()
    wall_start = time.perf_counter()
    try:
        consumer.start()
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não conectou ao MQTT")
        consumer.influx.connect()
        publisher.connect()

        for index in range(messages):
            device_id = f"sonda-{index % devices + 1:03d}"
            frame = consumer.state.next_simulator_frame(device_id)
            payload = make_uplink(
                device_id,
                frame,
                sensors[device_id].next_reading(rng),
                simulated_radio(100, rng),
            )
            decoded = payload["uplink_message"]["decoded_payload"]
            message_id = decoded["message_id"]
            generated_at = decoded["sent_at"]
            generated += 1
            publisher.publish(payload)
            published_at = iso_now()
            published += 1
            original[message_id] = payload
            traces[message_id] = {"generated_at": generated_at, "published_at": published_at}
            if rate:
                time.sleep(1 / rate)

        deadline = time.monotonic() + max(settings.mqtt_timeout, messages / 20)
        while time.monotonic() < deadline:
            counters = consumer.state.counters()
            received = counters.get("received", 0) - baseline.get("received", 0)
            finished = (
                counters.get("written", 0) - baseline.get("written", 0)
                + counters.get("rejected", 0) - baseline.get("rejected", 0)
                + counters.get("duplicates", 0) - baseline.get("duplicates", 0)
            )
            if received >= messages and finished >= messages:
                break
            time.sleep(0.1)

        expected_readings = {message_id: _flat_expected(payload) for message_id, payload in original.items()}
        stored_by_id: dict[str, dict[str, Any]] = {}
        query_deadline = time.monotonic() + 5
        while time.monotonic() < query_deadline:
            stored_by_id = {
                row["message_id"]: row
                for row in consumer.influx.query_since(started_at)
                if row.get("message_id") in expected_readings
            }
            if len(stored_by_id) == messages:
                break
            time.sleep(0.1)

        found = 0
        differences: dict[str, list[str]] = {}
        latencies = []
        for message_id, flat in expected_readings.items():
            stored = stored_by_id.get(message_id)
            diff = ["message_id não localizado"] if stored is None else consumer.influx.compare(flat, stored)
            ok = not diff
            consumer.state.stage(message_id, "published", occurred_at=traces[message_id]["published_at"])
            if ok:
                consumer.state.stage(message_id, "confirmed")
                consumer.state.increment("confirmed")
            trace = consumer.state.get_message(message_id) or {}
            traces[message_id].update({key: trace.get(key) for key in (
                "received_at", "validated_at", "written_at", "confirmed_at", "latency_ms"
            )})
            if ok:
                found += 1
                if trace.get("latency_ms") is not None:
                    latencies.append(trace["latency_ms"])
            else:
                differences[message_id] = diff

        counters = consumer.state.counters()
        actual = {
            "generated": generated,
            "published": published,
            "received": counters.get("received", 0) - baseline.get("received", 0),
            "valid": counters.get("valid", 0) - baseline.get("valid", 0),
            "rejected": counters.get("rejected", 0) - baseline.get("rejected", 0),
            "written": counters.get("written", 0) - baseline.get("written", 0),
            "found_in_influxdb": found,
            "duplicates": counters.get("duplicates", 0) - baseline.get("duplicates", 0),
        }
        actual["lost"] = messages - found
        elapsed = time.perf_counter() - wall_start
        actual["elapsed_seconds"] = elapsed
        actual["messages_per_second"] = found / elapsed if elapsed else 0
        actual.update(latency_stats(latencies))
        result["actual"] = actual
        result["differences"] = differences
        result["traces"] = traces
        exact = all((
            generated == messages,
            published == messages,
            actual["received"] == messages,
            actual["valid"] == messages,
            actual["written"] == messages,
            found == messages,
            actual["duplicates"] == 0,
        ))
        result["status"] = "PASS" if exact else "FAIL"
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
    finally:
        publisher.close()
        consumer.stop()
    return _finish(result, verbose)


def _flat_expected(payload: dict[str, Any]) -> dict[str, Any]:
    from consumer.parser import parse_uplink
    return parse_uplink(payload)


def _finish(result: dict[str, Any], verbose: bool) -> dict[str, Any]:
    result["finished_at"] = iso_now()
    evidence = save_artifact("evidence", "end_to_end", result)
    report_json, report_txt = save_report("end_to_end", result)
    result["evidence"] = str(evidence)
    result["reports"] = [str(report_json), str(report_txt)]
    if verbose:
        _print_result(result)
    return result


def _print_result(result: dict[str, Any]) -> None:
    print("=" * 60)
    print("END-TO-END TEST")
    print("SIMULATOR -> MQTT -> CONSUMER -> INFLUXDB -> QUERY")
    print("RADIO MODE: SIMULATED")
    print("PHYSICAL RANGE VALIDATION: NOT PERFORMED")
    print("=" * 60)
    actual = result.get("actual", {})
    for key, label in (
        ("generated", "Generated"), ("published", "Published"), ("received", "Received"),
        ("valid", "Valid"), ("written", "Written"), ("found_in_influxdb", "Found in InfluxDB"),
        ("lost", "Lost"), ("duplicates", "Duplicates"),
    ):
        print(f"{label:<30} {actual.get(key, 'NOT EXECUTED')}")
    print(f"\nRESULT: {result['status']}")
    if result.get("error"):
        print(f"Reason: {result['error']}")
    print(f"Evidence: {result['evidence']}")


@pytest.mark.integration
def test_100_messages_end_to_end():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 e configure MQTT/InfluxDB")
    result = run_end_to_end(verbose=False)
    assert result["status"] == "PASS", result.get("error") or result.get("actual")


if __name__ == "__main__":
    outcome = run_end_to_end()
    raise SystemExit(0 if outcome["status"] == "PASS" else 2 if outcome["status"] == "NOT EXECUTED" else 1)
