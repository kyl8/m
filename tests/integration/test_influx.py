from __future__ import annotations

import os
from uuid import uuid4

import pytest

from config import get_settings
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from project_io import iso_now, save_artifact, save_report


def perform_influx_test(verbose: bool = True) -> dict:
    settings = get_settings()
    message_id = str(uuid4())
    reading = {
        "device_id": "sonda-influx-test",
        "message_id": message_id,
        "frame_counter": 1,
        "site": "laboratorio",
        "source": "simulator",
        "gateway_id": "gateway-test",
        "sent_at": iso_now(),
        "received_at": iso_now(),
        "temperature_c": 25.123456,
        "ph": 7.654321,
    }
    result = {
        "test": "INFLUX BASIC",
        "started_at": iso_now(),
        "status": "NOT EXECUTED",
        "expected": {"message_id": message_id, "temperature_c": 25.123456, "ph": 7.654321},
        "actual": {},
    }
    writer = InfluxWriter(settings)
    try:
        if not settings.influx_configured:
            raise InfluxUnavailable("configure INFLUX_TOKEN, INFLUX_ORG e INFLUX_BUCKET no .env")
        result["detected_version"] = writer.connect()
        writer.write(reading)
        ok, stored, differences = writer.verify(reading)
        result["actual"] = stored or {}
        result["differences"] = differences
        result["status"] = "PASS" if ok else "FAIL"
    except InfluxUnavailable as exc:
        result["error"] = str(exc)
    finally:
        writer.close()
    result["finished_at"] = iso_now()
    evidence = save_artifact("evidence", "influx", result)
    reports = save_report("influx", result)
    result["evidence"] = str(evidence)
    result["reports"] = [str(path) for path in reports]
    if verbose:
        _print(result)
    return result


def _print(result: dict) -> None:
    status = result["status"]
    pass_mark = "PASS" if status == "PASS" else status
    actual = result.get("actual", {})
    print(f"WRITE........................ {pass_mark}")
    print(f"QUERY........................ {pass_mark}")
    print(f"MESSAGE ID................... {'PASS' if actual.get('message_id') == result['expected']['message_id'] else pass_mark}")
    print(f"TEMPERATURE.................. {'PASS' if actual.get('temperature_c') == 25.123456 else pass_mark}")
    print(f"PH........................... {'PASS' if actual.get('ph') == 7.654321 else pass_mark}")
    print(f"\nDATA INTEGRITY............... {pass_mark}")
    if result.get("detected_version"):
        print(f"InfluxDB detected version: {result['detected_version']}")
    if result.get("error"):
        print(f"Motivo: {result['error']}")
    print(f"Evidência: {result['evidence']}")


@pytest.mark.integration
def test_influx_write_query_integrity():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 e configure o InfluxDB")
    result = perform_influx_test(verbose=False)
    assert result["status"] == "PASS", result.get("error") or result.get("differences")


if __name__ == "__main__":
    outcome = perform_influx_test()
    raise SystemExit(0 if outcome["status"] == "PASS" else 2 if outcome["status"] == "NOT EXECUTED" else 1)
