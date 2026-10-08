from __future__ import annotations

import argparse
import random
import time
from typing import Any

from config import get_settings
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from consumer.parser import parse_uplink
from project_io import iso_now, latency_stats, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState


def run_batch_comparison(total: int = 1000, batch_sizes: list[int] | None = None) -> dict[str, Any]:
    sizes = batch_sizes or [1, 10, 100, 500, 1000]
    settings = get_settings()
    report: dict[str, Any] = {
        "test": "INFLUX BATCH COMPARISON",
        "started_at": iso_now(),
        "status": "NOT EXECUTED",
        "total_per_batch_size": total,
        "results": [],
    }
    if not settings.influx_configured:
        report["error"] = "InfluxDB não configurado"
        return _finish(report)
    writer = InfluxWriter(settings)
    try:
        report["detected_version"] = writer.connect()
        for batch_size in sizes:
            batch_started_at = iso_now()
            readings = _readings(total, batch_size)
            batch_latencies = []
            errors = 0
            start = time.perf_counter()
            for offset in range(0, total, batch_size):
                before = time.perf_counter()
                try:
                    writer.write_many(readings[offset:offset + batch_size])
                except InfluxUnavailable:
                    errors += 1
                batch_latencies.append((time.perf_counter() - before) * 1000)
            elapsed = time.perf_counter() - start
            expected_ids = {reading["message_id"] for reading in readings}
            stored = {row.get("message_id") for row in writer.query_since(batch_started_at)}
            found = len(expected_ids & stored)
            report["results"].append({
                "batch_size": batch_size,
                "total": total,
                "found": found,
                "errors": errors,
                "elapsed_seconds": elapsed,
                "throughput_msg_s": total / elapsed if elapsed else 0,
                **latency_stats(batch_latencies),
            })
        report["status"] = "PASS" if all(
            row["found"] == total and row["errors"] == 0 for row in report["results"]
        ) else "FAIL"
    except InfluxUnavailable as exc:
        report["error"] = str(exc)
    finally:
        writer.close()
    return _finish(report)


def _readings(total: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    state = SensorState.create(rng)
    readings = []
    for frame in range(1, total + 1):
        payload = make_uplink(
            f"sonda-batch-{seed}", frame, state.next_reading(rng), simulated_radio(100, rng), site="batch-test"
        )
        readings.append(parse_uplink(payload))
    return readings


def _finish(report: dict[str, Any]) -> dict[str, Any]:
    report["finished_at"] = iso_now()
    paths = save_report("batch_comparison", report)
    evidence = save_artifact("evidence", "batch_comparison", report)
    print("BATCH | FOUND | ERRORS | MSG/S | AVG BATCH MS | P95")
    print("-" * 62)
    for row in report["results"]:
        print(
            f"{row['batch_size']:>5} | {row['found']:>5} | {row['errors']:>6} | "
            f"{row['throughput_msg_s']:>5.1f} | {row['average_ms']:>12.2f} | {row['p95_ms']:>5.2f}"
        )
    print(f"RESULT: {report['status']}")
    if report.get("error"):
        print(f"Reason: {report['error']}")
    print(f"Reports: {paths[0]}, {paths[1]}")
    print(f"Evidence: {evidence}")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--total", type=int, default=1000)
    args = parser.parse_args()
    run_batch_comparison(args.total)
