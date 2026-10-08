from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any

import pytest

from config import ROOT
from project_io import iso_now
from tests.integration.test_end_to_end import run_end_to_end

SAFE_MAX_MESSAGES = 500_000
SAFE_MAX_DEVICES = 1000


def run_load(devices: int, messages: int, rate: float = 0) -> dict[str, Any]:
    if not 1 <= devices <= SAFE_MAX_DEVICES:
        raise ValueError(f"devices deve estar entre 1 e {SAFE_MAX_DEVICES}")
    if not 1 <= messages <= SAFE_MAX_MESSAGES:
        raise ValueError(f"messages deve estar entre 1 e {SAFE_MAX_MESSAGES}")
    print("=" * 60)
    print("BACKEND STRESS TEST")
    print("THIS DOES NOT REPRESENT LORAWAN AIR TRAFFIC")
    print("RADIO MODE: SIMULATED")
    print("PHYSICAL RANGE VALIDATION: NOT PERFORMED")
    print("=" * 60)
    return run_end_to_end(messages=messages, devices=devices, rate=rate, verbose=True)


def run_scale(device_counts: list[int], messages_per_device: int) -> list[dict[str, Any]]:
    rows = []
    for devices in device_counts:
        total = devices * messages_per_device
        outcome = run_load(devices, total)
        actual = outcome.get("actual", {})
        rows.append({
            "devices": devices,
            "messages": total,
            "received": actual.get("received"),
            "stored": actual.get("found_in_influxdb"),
            "loss": actual.get("lost"),
            "messages_per_second": actual.get("messages_per_second"),
            "average_latency_ms": actual.get("average_ms"),
            "p95_ms": actual.get("p95_ms"),
            "status": outcome["status"],
        })
        if outcome["status"] != "PASS":
            break
    _save_scale_csv(rows)
    print("\nDEVICES | MSGS | RECEIVED | STORED | LOSS | MSG/S | P95")
    print("-" * 68)
    for row in rows:
        print(
            f"{row['devices']:>7} | {row['messages']:>4} | {row['received']!s:>8} | "
            f"{row['stored']!s:>6} | {row['loss']!s:>4} | "
            f"{_fmt(row['messages_per_second']):>5} | {_fmt(row['p95_ms']):>5}"
        )
    return rows


def _save_scale_csv(rows: list[dict[str, Any]]) -> Path:
    folder = ROOT / "reports"
    folder.mkdir(exist_ok=True)
    path = folder / f"{iso_now().replace(':', '').replace('-', '')}_scale.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["devices"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV: {path}")
    return path


def _fmt(value: Any) -> str:
    return "-" if value is None else f"{value:.1f}"


@pytest.mark.load
def test_opt_in_load():
    if os.getenv("RUN_LOAD_TESTS") != "1":
        pytest.skip("defina RUN_LOAD_TESTS=1; o teste publica e consulta dados reais")
    outcome = run_load(10, 1000)
    assert outcome["status"] == "PASS"


def main() -> None:
    parser = argparse.ArgumentParser(description="Teste verificável MQTT -> Consumer -> InfluxDB")
    parser.add_argument("--devices", type=int, default=10)
    parser.add_argument("--messages", type=int, default=1000)
    parser.add_argument("--rate", type=float, default=0, help="limite de publicações por segundo; 0 sem limite")
    parser.add_argument("--scale", action="store_true", help="executa 1, 10, 50, 100 e 500 dispositivos")
    parser.add_argument("--messages-per-device", type=int, default=10)
    args = parser.parse_args()
    if args.scale:
        run_scale([1, 10, 50, 100, 500], args.messages_per_device)
    else:
        run_load(args.devices, args.messages, args.rate)


if __name__ == "__main__":
    main()
