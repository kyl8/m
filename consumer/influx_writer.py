from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from config import Settings
from project_io import parse_time


class InfluxUnavailable(RuntimeError):
    pass


class InfluxWriter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: InfluxDBClient | None = None
        self.write_api = None

    def detected_version(self) -> str:
        request = Request(self.settings.influx_url.rstrip("/") + "/health")
        try:
            with urlopen(request, timeout=self.settings.influx_timeout_ms / 1000) as response:
                data = json.loads(response.read().decode("utf-8"))
                return str(data.get("version") or data.get("message") or "desconhecida")
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise InfluxUnavailable(str(exc)) from exc

    def connect(self) -> str:
        if not self.settings.influx_configured:
            raise InfluxUnavailable("INFLUX_TOKEN, INFLUX_ORG e INFLUX_BUCKET são obrigatórios")
        version = self.detected_version()
        if version.startswith(("1.", "3.")):
            raise InfluxUnavailable(
                f"InfluxDB {version} detectado; esta POC usa a API 2.x. Selecione uma instância 2.x ou implemente o adaptador correspondente."
            )
        self.client = InfluxDBClient(
            url=self.settings.influx_url,
            token=self.settings.influx_token,
            org=self.settings.influx_org,
            timeout=self.settings.influx_timeout_ms,
        )
        if not self.client.ping():
            raise InfluxUnavailable("servidor respondeu, mas o ping falhou")
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        return version

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.write_api = None

    def write(self, reading: dict[str, Any]) -> None:
        if self.client is None:
            self.connect()
        point = self._point(reading)
        try:
            self.write_api.write(
                bucket=self.settings.influx_bucket,
                org=self.settings.influx_org,
                record=point,
                write_precision=WritePrecision.NS,
            )
        except Exception as exc:
            self.close()
            raise InfluxUnavailable(str(exc)) from exc

    def write_many(self, readings: list[dict[str, Any]]) -> None:
        if self.client is None:
            self.connect()
        points = [self._point(reading) for reading in readings]
        try:
            self.write_api.write(
                bucket=self.settings.influx_bucket,
                org=self.settings.influx_org,
                record=points,
                write_precision=WritePrecision.NS,
            )
        except Exception as exc:
            self.close()
            raise InfluxUnavailable(str(exc)) from exc

    def query_message(self, message_id: str, days: int = 30) -> dict[str, Any] | None:
        if self.client is None:
            self.connect()
        safe_id = message_id.replace("\\", "\\\\").replace('"', '\\"')
        safe_measurement = "water_quality"
        flux = f'''
from(bucket: "{self.settings.influx_bucket}")
  |> range(start: -{int(days)}d)
  |> filter(fn: (r) => r._measurement == "{safe_measurement}")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => r.message_id == "{safe_id}")
  |> limit(n: 1)
'''
        try:
            tables = self.client.query_api().query(flux, org=self.settings.influx_org)
        except Exception as exc:
            self.close()
            raise InfluxUnavailable(str(exc)) from exc
        for table in tables:
            for record in table.records:
                return self._record_values(record.values)
        return None

    def query_since(self, started_at: str) -> list[dict[str, Any]]:
        if self.client is None:
            self.connect()
        normalized = parse_time(started_at).isoformat().replace("+00:00", "Z")
        flux = f'''
from(bucket: "{self.settings.influx_bucket}")
  |> range(start: time(v: "{normalized}"))
  |> filter(fn: (r) => r._measurement == "water_quality")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
'''
        try:
            tables = self.client.query_api().query(flux, org=self.settings.influx_org)
        except Exception as exc:
            self.close()
            raise InfluxUnavailable(str(exc)) from exc
        return [self._record_values(record.values) for table in tables for record in table.records]

    def verify(
        self, original: dict[str, Any], wait_seconds: float = 5.0
    ) -> tuple[bool, dict[str, Any] | None, list[str]]:
        deadline = time.monotonic() + wait_seconds
        stored = self.query_message(original["message_id"])
        while stored is None and time.monotonic() < deadline:
            time.sleep(0.1)
            stored = self.query_message(original["message_id"])
        if stored is None:
            return False, None, ["message_id não localizado"]
        differences = []
        differences.extend(self.compare(original, stored))
        return not differences, stored, differences

    @staticmethod
    def compare(original: dict[str, Any], stored: dict[str, Any]) -> list[str]:
        differences = []
        for field in (
            "device_id", "message_id", "temperature_c", "ph", "turbidity_ntu",
            "conductivity_us_cm", "dissolved_oxygen_mg_l", "frame_counter",
        ):
            expected = original.get(field)
            if expected is not None and stored.get(field) != expected:
                differences.append(f"{field}: enviado={expected!r}, armazenado={stored.get(field)!r}")
        return differences

    @staticmethod
    def _record_values(values: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(values)
        cleaned["received_at"] = cleaned.pop("_time", None)
        return {key: value for key, value in cleaned.items() if not key.startswith("_")}

    @staticmethod
    def _point(reading: dict[str, Any]) -> Point:
        point = Point("water_quality")
        for tag in ("device_id", "gateway_id", "site", "source"):
            if reading.get(tag) is not None:
                point.tag(tag, str(reading[tag]))
        for field in (
            "message_id", "temperature_c", "ph", "turbidity_ntu", "conductivity_us_cm",
            "dissolved_oxygen_mg_l", "rssi_dbm", "snr_db", "latency_ms", "distance_m",
            "frame_counter", "frequency_hz", "spreading_factor", "bandwidth_hz", "sent_at",
        ):
            if reading.get(field) is not None:
                point.field(field, reading[field])
        point.time(parse_time(reading["received_at"]), WritePrecision.NS)
        return point
