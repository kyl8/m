from __future__ import annotations

import time
from uuid import uuid4

from config import get_settings
from mqtt.publisher import publish_once
from mqtt.subscriber import MqttSubscriber
from project_io import iso_now, save_artifact, save_report


def run_mqtt_check(verbose: bool = True) -> dict:
    settings = get_settings()
    message_id = str(uuid4())
    topic = settings.mqtt_topic.rstrip("/") + "/poc-test"
    payload = {"test": "mqtt-round-trip", "message_id": message_id, "sent_at": iso_now()}
    started_at = iso_now()
    subscriber = MqttSubscriber(settings, topic, client_id=f"mqtt-check-sub-{message_id[:8]}")
    result = {
        "test": "MQTT BASIC",
        "started_at": started_at,
        "status": "NOT EXECUTED",
        "expected": {"message_id": message_id},
        "actual": {},
    }
    start = time.perf_counter()
    try:
        subscriber.start()
        result["status"] = "FAIL"
        publish_once(payload, settings, topic)
        received, received_clock = subscriber.wait()
        latency_ms = (received_clock - start) * 1000
        matched = received.get("message_id") == message_id
        result["actual"] = {"message_id": received.get("message_id"), "latency_ms": latency_ms}
        result["status"] = "PASS" if matched else "FAIL"
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        result["error"] = str(exc)
    finally:
        subscriber.stop()
    result["finished_at"] = iso_now()
    evidence = save_artifact("evidence", "mqtt", result)
    reports = save_report("mqtt", result)
    result["evidence"] = str(evidence)
    result["reports"] = [str(path) for path in reports]
    if verbose:
        _print_result(result)
    return result


def _print_result(result: dict) -> None:
    passed = result["status"] == "PASS"
    mark = "PASS" if passed else result["status"]
    print("BROKER CONNECTION............ " + mark)
    print("PUBLISH...................... " + mark)
    print("SUBSCRIBE.................... " + mark)
    print("MESSAGE ID................... " + mark)
    print("ROUND TRIP................... " + mark)
    if "latency_ms" in result.get("actual", {}):
        print(f"\nLatency: {result['actual']['latency_ms']:.2f} ms")
    if result.get("error"):
        print(f"\nErro: {result['error']}")
    print(f"Evidência: {result['evidence']}")


if __name__ == "__main__":
    run_mqtt_check()
