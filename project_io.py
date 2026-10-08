from __future__ import annotations

import json
import math
import statistics
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import ROOT


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def latency_stats(values: Iterable[float]) -> dict[str, float | None]:
    data = list(values)
    if not data:
        return {key: None for key in ("average_ms", "p50_ms", "p95_ms", "p99_ms", "min_ms", "max_ms")}
    return {
        "average_ms": statistics.fmean(data),
        "p50_ms": percentile(data, 0.50),
        "p95_ms": percentile(data, 0.95),
        "p99_ms": percentile(data, 0.99),
        "min_ms": min(data),
        "max_ms": max(data),
    }


def save_artifact(folder: str, name: str, data: dict[str, Any]) -> Path:
    target = ROOT / folder
    target.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%d_%H%M%S_%f")
    path = target / f"{stamp}_{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def save_report(name: str, data: dict[str, Any]) -> tuple[Path, Path]:
    json_path = save_artifact("reports", name, data)
    txt_path = json_path.with_suffix(".txt")
    lines = [f"{key}: {value}" for key, value in data.items()]
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, txt_path

