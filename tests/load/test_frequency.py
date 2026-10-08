from __future__ import annotations

import argparse
import csv
from typing import Any

from config import ROOT
from project_io import iso_now, save_artifact, save_report
from tests.integration.test_end_to_end import run_end_to_end

SAFE_RATES = (1, 10, 100, 500, 1000)


def run_frequency_comparison(messages_per_rate: int = 1000) -> list[dict[str, Any]]:
    started_at = iso_now()
    rows = []
    for rate in SAFE_RATES:
        print(f"\n[INFO] Testando taxa de publicação alvo: {rate} msg/s")
        outcome = run_end_to_end(messages_per_rate, devices=100, rate=rate, verbose=False)
        actual = outcome.get("actual", {})
        row = {
            "target_msg_s": rate,
            "messages": messages_per_rate,
            "status": outcome["status"],
            "stored": actual.get("found_in_influxdb"),
            "loss": actual.get("lost"),
            "observed_msg_s": actual.get("messages_per_second"),
            "average_latency_ms": actual.get("average_ms"),
            "p95_ms": actual.get("p95_ms"),
            "p99_ms": actual.get("p99_ms"),
        }
        rows.append(row)
        if outcome["status"] != "PASS":
            print("[WARNING] Progressão interrompida após o primeiro resultado diferente de PASS.")
            break
        if actual.get("p95_ms") and actual["p95_ms"] > 10_000:
            print("[WARNING] P95 excedeu o limite de segurança de 10 segundos; progressão interrompida.")
            break
    _finish(rows, started_at)
    return rows


def _finish(rows: list[dict[str, Any]], started_at: str) -> None:
    payload = {
        "test": "FREQUENCY COMPARISON",
        "started_at": started_at,
        "finished_at": iso_now(),
        "status": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
        "safety_limits": {"max_rate_msg_s": 1000, "stop_p95_ms": 10_000},
        "results": rows,
    }
    paths = save_report("frequency_comparison", payload)
    evidence = save_artifact("evidence", "frequency_comparison", payload)
    csv_path = ROOT / "reports" / f"{iso_now().replace(':', '').replace('-', '')}_frequency.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["target_msg_s"])
        writer.writeheader()
        writer.writerows(rows)
    print("TARGET | STORED | LOSS | OBSERVED MSG/S | AVG MS | P95 | P99")
    print("-" * 68)
    for row in rows:
        print(
            f"{row['target_msg_s']:>6} | {row['stored']!s:>6} | {row['loss']!s:>4} | "
            f"{_fmt(row['observed_msg_s']):>14} | {_fmt(row['average_latency_ms']):>6} | "
            f"{_fmt(row['p95_ms']):>5} | {_fmt(row['p99_ms']):>5}"
        )
    print(f"Reports: {paths[0]}, {paths[1]}, {csv_path}")
    print(f"Evidence: {evidence}")


def _fmt(value: Any) -> str:
    return "-" if value is None else f"{value:.1f}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages-per-rate", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.messages_per_rate <= 100_000:
        raise SystemExit("messages-per-rate deve estar entre 1 e 100000")
    run_frequency_comparison(args.messages_per_rate)
