from __future__ import annotations

import os
import random
import time

import pytest

from config import get_settings
from consumer.consumer import Consumer
from consumer.parser import parse_uplink
from mqtt.publisher import MqttPublisher
from project_io import iso_now, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def run_consumer_restart_test(verbose: bool = True) -> dict:
    settings = get_settings()
    result = {
        "test": "CONSUMER RESTART",
        "started_at": iso_now(),
        "status": "NOT EXECUTED",
        "expected": {"before_restart_confirmed": True, "after_restart_confirmed": True},
        "actual": {},
    }
    if not settings.influx_configured:
        result["error"] = "InfluxDB não configurado"
        return _finish(result, verbose)

    rng = random.Random()
    sensor = SensorState.create(rng)
    publisher = MqttPublisher(settings, "consumer-restart-test")
    consumer = Consumer(settings)
    readings = []
    try:
        publisher.connect()
        for cycle in (1, 2):
            consumer.start()
            if not consumer.connected.wait(settings.mqtt_timeout):
                raise TimeoutError(f"consumer não conectou no ciclo {cycle}")
            device_id = "sonda-restart-test"
            frame = consumer.state.next_simulator_frame(device_id)
            payload = make_uplink(device_id, frame, sensor.next_reading(rng), simulated_radio(100, rng))
            publisher.publish(payload)
            reading = parse_uplink(payload)
            readings.append(reading)
            deadline = time.monotonic() + settings.mqtt_timeout
            while time.monotonic() < deadline:
                trace = consumer.state.get_message(reading["message_id"])
                if trace and trace.get("written_at"):
                    break
                time.sleep(0.1)
            consumer.stop()
            if cycle == 1:
                consumer = Consumer(settings)

        confirmed = []
        for reading in readings:
            ok, _, _ = consumer.influx.verify(reading)
            confirmed.append(ok)
        result["actual"] = {
            "before_restart_confirmed": confirmed[0],
            "after_restart_confirmed": confirmed[1],
            "pending_after_restart": consumer.queue.count(),
        }
        result["status"] = "PASS" if all(confirmed) and consumer.queue.count() == 0 else "FAIL"
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        result["status"] = "FAIL"
        result["error"] = str(exc)
    finally:
        publisher.close()
        consumer.stop()
    return _finish(result, verbose)


def _finish(result: dict, verbose: bool) -> dict:
    result["finished_at"] = iso_now()
    result["evidence"] = str(save_artifact("evidence", "consumer_restart", result))
    result["reports"] = [str(path) for path in save_report("consumer_restart", result)]
    if verbose:
        print(f"CONSUMER STOP/START............ {result['status']}")
        print(f"DATABASE CONFIRMATION.......... {result['status']}")
        if result.get("error"):
            print(f"Reason: {result['error']}")
        print(f"Evidence: {result['evidence']}")
    return result


@pytest.mark.integration
def test_consumer_restart_with_real_services():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 para reiniciar o consumer com serviços reais")
    outcome = run_consumer_restart_test(verbose=False)
    assert outcome["status"] == "PASS", outcome


if __name__ == "__main__":
    outcome = run_consumer_restart_test()
    raise SystemExit(0 if outcome["status"] == "PASS" else 2 if outcome["status"] == "NOT EXECUTED" else 1)

