from __future__ import annotations

import os

import pytest

from mqtt.mqtt_check import run_mqtt_check


@pytest.mark.integration
def test_mqtt_round_trip():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 para usar o broker MQTT configurado")
    result = run_mqtt_check(verbose=False)
    assert result["status"] == "PASS", result.get("error")


if __name__ == "__main__":
    result = run_mqtt_check()
    raise SystemExit(0 if result["status"] == "PASS" else 2 if result["status"] == "NOT EXECUTED" else 1)
