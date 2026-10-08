from __future__ import annotations

import os
import random
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest

from config import ROOT, get_settings
from consumer.consumer import Consumer
from consumer.parser import parse_uplink
from mqtt.publisher import MqttPublisher
from project_io import iso_now, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def run_mqtt_reconnect_test(verbose: bool = True) -> dict:
    settings = replace(get_settings(), mqtt_port=1884, mqtt_timeout=10)
    mosquitto = _find_mosquitto()
    config = ROOT / "mqtt" / "mosquitto_test.conf"
    result = {
        "test": "MQTT OUTAGE AND RECONNECT",
        "started_at": iso_now(),
        "status": "NOT EXECUTED",
        "expected": {"offline_detected": True, "reconnected": True, "database_confirmed": True},
        "actual": {},
    }
    if mosquitto is None:
        result["error"] = "mosquitto.exe não localizado"
        return _finish(result, verbose)

    first_broker = _start_broker(mosquitto, config)
    consumer = Consumer(settings)
    publisher = MqttPublisher(settings, "mqtt-reconnect-publisher")
    second_broker = None
    try:
        _wait_port(1884, online=True)
        consumer.start()
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não conectou ao broker de teste")
        connected_at = iso_now()

        _stop_broker(first_broker)
        _wait_port(1884, online=False)
        deadline = time.monotonic() + settings.mqtt_timeout
        while consumer.connected.is_set() and time.monotonic() < deadline:
            time.sleep(0.1)
        offline_at = iso_now()
        offline_detected = not consumer.connected.is_set()

        second_broker = _start_broker(mosquitto, config)
        _wait_port(1884, online=True)
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não reconectou após o retorno do broker")
        reconnected_at = iso_now()

        rng = random.Random()
        device_id = "sonda-mqtt-reconnect"
        frame = consumer.state.next_simulator_frame(device_id)
        payload = make_uplink(
            device_id, frame, SensorState.create(rng).next_reading(rng), simulated_radio(100, rng)
        )
        reading = parse_uplink(payload)
        publisher.connect()
        publisher.publish(payload)
        published_at = iso_now()

        deadline = time.monotonic() + settings.mqtt_timeout
        while time.monotonic() < deadline:
            trace = consumer.state.get_message(reading["message_id"])
            if trace and trace.get("written_at"):
                break
            time.sleep(0.1)
        verified, stored, differences = consumer.influx.verify(reading)
        confirmed_at = iso_now() if verified else None
        result["actual"] = {
            "connected_at": connected_at,
            "offline_at": offline_at,
            "offline_detected": offline_detected,
            "consumer_alive_while_offline": True,
            "reconnected_at": reconnected_at,
            "published_at": published_at,
            "message_id": reading["message_id"],
            "database_confirmed_at": confirmed_at,
            "database_confirmed": verified,
            "differences": differences,
            "stored_message_id": stored.get("message_id") if stored else None,
        }
        result["status"] = "PASS" if offline_detected and verified else "FAIL"
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
    finally:
        publisher.close()
        consumer.stop()
        if first_broker.poll() is None:
            _stop_broker(first_broker)
        if second_broker and second_broker.poll() is None:
            _stop_broker(second_broker)
    return _finish(result, verbose)


def _find_mosquitto() -> Path | None:
    candidates = [
        Path(os.getenv("MOSQUITTO_EXE", "")),
        Path(r"D:\Program Files\Mosquitto\mosquitto.exe"),
        Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "mosquitto" / "mosquitto.exe",
    ]
    return next((path for path in candidates if path.is_file()), None)


def _start_broker(executable: Path, config: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(executable), "-c", str(config)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _stop_broker(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_port(port: int, *, online: bool) -> None:
    import socket

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                current = True
        except OSError:
            current = False
        if current == online:
            return
        time.sleep(0.1)
    raise TimeoutError(f"porta {port} não atingiu estado online={online}")


def _finish(result: dict, verbose: bool) -> dict:
    result["finished_at"] = iso_now()
    result["evidence"] = str(save_artifact("evidence", "mqtt_reconnect", result))
    result["reports"] = [str(path) for path in save_report("mqtt_reconnect", result)]
    if verbose:
        print(f"MQTT OFFLINE DETECTED.......... {_mark(result, 'offline_detected')}")
        print(f"AUTOMATIC RECONNECT........... {_mark(result, 'reconnected_at')}")
        print(f"DATABASE CONFIRMATION......... {_mark(result, 'database_confirmed')}")
        print(f"RESULT: {result['status']}")
        if result.get("error"):
            print(f"Reason: {result['error']}")
        print(f"Evidence: {result['evidence']}")
    return result


def _mark(result: dict, field: str) -> str:
    return "PASS" if result.get("actual", {}).get(field) else result["status"]


@pytest.mark.integration
def test_mqtt_outage_and_automatic_reconnect():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 para controlar um broker de teste na porta 1884")
    outcome = run_mqtt_reconnect_test(verbose=False)
    assert outcome["status"] == "PASS", outcome


if __name__ == "__main__":
    outcome = run_mqtt_reconnect_test()
    raise SystemExit(0 if outcome["status"] == "PASS" else 2 if outcome["status"] == "NOT EXECUTED" else 1)

