from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from config import get_settings
from consumer.consumer import Consumer
from consumer.influx_writer import InfluxWriter
from mqtt.publisher import MqttPublisher, PublishError
from project_io import iso_now, save_artifact, save_report


def run_influx_outage_and_optional_recovery() -> dict:
    normal = get_settings()
    with tempfile.TemporaryDirectory() as folder:
        temporary = Path(folder)
        offline = replace(
            normal,
            influx_url="http://127.0.0.1:1",
            influx_token="failure-test-token",
            influx_org="failure-test-org",
            influx_bucket="failure-test-bucket",
            pending_db=temporary / "pending.db",
            state_db=temporary / "state.db",
            influx_timeout_ms=500,
        )
        consumer = Consumer(offline)
        reading = {
            "device_id": "sonda-failure-test",
            "message_id": str(uuid4()),
            "frame_counter": 1,
            "site": "laboratorio",
            "source": "simulator",
            "gateway_id": "gateway-test",
            "sent_at": iso_now(),
            "received_at": iso_now(),
            "temperature_c": 25.0,
            "ph": 7.5,
            "latency_ms": 0.0,
        }
        consumer.state.first_seen(reading)
        consumer._store(reading)
        queued = consumer.queue.count() == 1
        recovered = False
        recovery_status = "NOT EXECUTED"
        if normal.influx_configured:
            consumer.influx = InfluxWriter(normal)
            count, total = consumer.recover_pending()
            recovered = count == total == 1 and consumer.queue.count() == 0
            recovery_status = "PASS" if recovered else "FAIL"
        full_status = "PASS" if queued and recovered else "NOT EXECUTED" if queued else "FAIL"
        result = {
            "test": "INFLUX FAILURE AND RECOVERY",
            "started_at": reading["sent_at"],
            "finished_at": iso_now(),
            "status": full_status,
            "expected": {"queued_while_offline": True, "confirmed_after_recovery": True},
            "actual": {"queued_while_offline": queued, "recovery": recovery_status},
        }
        evidence = save_artifact("evidence", "failure_recovery", result)
        result["reports"] = [str(path) for path in save_report("failure_recovery", result)]
        result["evidence"] = str(evidence)
        return result


def run_mqtt_unavailable_detection() -> dict:
    settings = replace(get_settings(), mqtt_host="127.0.0.1", mqtt_port=1, mqtt_timeout=1)
    publisher = MqttPublisher(settings, "mqtt-offline-test")
    detected = False
    error = None
    try:
        publisher.connect()
    except PublishError as exc:
        detected = True
        error = str(exc)
    finally:
        publisher.close()
    result = {
        "test": "MQTT UNAVAILABLE",
        "started_at": iso_now(),
        "finished_at": iso_now(),
        "status": "PASS" if detected else "FAIL",
        "expected": {"offline_detected": True},
        "actual": {"offline_detected": detected, "error": error, "reconnection_after_real_restart": "NOT TESTED"},
    }
    result["evidence"] = str(save_artifact("evidence", "mqtt_failure", result))
    result["reports"] = [str(path) for path in save_report("mqtt_failure", result)]
    return result


if __name__ == "__main__":
    print(run_influx_outage_and_optional_recovery())
    print(run_mqtt_unavailable_detection())
