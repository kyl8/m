from __future__ import annotations

import os
import random
import time

import pytest

from config import get_settings
from consumer.consumer import Consumer
from mqtt.publisher import MqttPublisher
from project_io import iso_now, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def run_message_rules_test(verbose: bool = True) -> dict:
    settings = get_settings()
    consumer = Consumer(settings)
    publisher = MqttPublisher(settings, "message-rules-test")
    baseline = consumer.state.counters()
    rng = random.Random()
    sensor = SensorState.create(rng)
    started_at = iso_now()
    run_suffix = started_at.replace(":", "").replace(".", "")[-10:]
    status = "NOT EXECUTED"
    error = None
    try:
        consumer.start()
        if not consumer.connected.wait(settings.mqtt_timeout):
            raise TimeoutError("consumer não conectou ao MQTT")
        publisher.connect()

        duplicate = make_uplink(
            f"sonda-duplicate-{run_suffix}", 1, sensor.next_reading(rng), simulated_radio(100, rng)
        )
        publisher.publish(duplicate)
        publisher.publish(duplicate)

        for frame in (10, 12, 11):
            publisher.publish(
                make_uplink(
                    f"sonda-order-{run_suffix}", frame, sensor.next_reading(rng), simulated_radio(100, rng)
                )
            )
        for frame in (20, 23):
            publisher.publish(
                make_uplink(
                    f"sonda-loss-{run_suffix}", frame, sensor.next_reading(rng), simulated_radio(100, rng)
                )
            )

        deadline = time.monotonic() + settings.mqtt_timeout
        while time.monotonic() < deadline:
            current = consumer.state.counters()
            completed = all((
                current.get("received", 0) - baseline.get("received", 0) >= 7,
                current.get("duplicates", 0) - baseline.get("duplicates", 0) >= 1,
                current.get("out_of_order", 0) - baseline.get("out_of_order", 0) >= 1,
                current.get("possible_loss", 0) - baseline.get("possible_loss", 0) >= 3,
                current.get("written", 0) - baseline.get("written", 0) >= 6,
            ))
            if completed:
                break
            time.sleep(0.1)
        current = consumer.state.counters()
        actual = {
            "received": current.get("received", 0) - baseline.get("received", 0),
            "duplicates": current.get("duplicates", 0) - baseline.get("duplicates", 0),
            "out_of_order": current.get("out_of_order", 0) - baseline.get("out_of_order", 0),
            "possible_missing_frames": current.get("possible_loss", 0) - baseline.get("possible_loss", 0),
        }
        status = "PASS" if actual == {
            "received": 7,
            "duplicates": 1,
            "out_of_order": 1,
            "possible_missing_frames": 3,
        } else "FAIL"
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        actual = {}
        error = str(exc)
    finally:
        publisher.close()
        consumer.stop()
    result = {
        "test": "DUPLICATE AND FRAME ORDER",
        "started_at": started_at,
        "finished_at": iso_now(),
        "status": status,
        "expected": {"received": 7, "duplicates": 1, "out_of_order": 1, "possible_missing_frames": 3},
        "actual": actual,
        "error": error,
    }
    result["evidence"] = str(save_artifact("evidence", "message_rules", result))
    result["reports"] = [str(path) for path in save_report("message_rules", result)]
    if verbose:
        print(f"DUPLICATE DETECTED............ {'PASS' if actual.get('duplicates') == 1 else status}")
        print(f"OUT OF ORDER................. {'PASS' if actual.get('out_of_order') == 1 else status}")
        print(f"POSSIBLE PACKET LOSS......... {'PASS' if actual.get('possible_missing_frames') == 3 else status}")
        print(f"RESULT: {status}")
        if error:
            print(f"Reason: {error}")
        print(f"Evidence: {result['evidence']}")
    return result


@pytest.mark.integration
def test_duplicate_and_frame_order_over_real_mqtt():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 para publicar regras no MQTT real")
    result = run_message_rules_test(verbose=False)
    assert result["status"] == "PASS", result


if __name__ == "__main__":
    outcome = run_message_rules_test()
    raise SystemExit(0 if outcome["status"] == "PASS" else 2 if outcome["status"] == "NOT EXECUTED" else 1)
