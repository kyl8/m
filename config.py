from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    mqtt_host: str = os.getenv("MQTT_HOST", "localhost")
    mqtt_port: int = _int("MQTT_PORT", 1883)
    mqtt_username: str = os.getenv("MQTT_USERNAME", "")
    mqtt_password: str = os.getenv("MQTT_PASSWORD", "")
    mqtt_topic: str = os.getenv("MQTT_TOPIC", "portos/lorawan/uplink")
    mqtt_qos: int = _int("MQTT_QOS", 1)
    mqtt_timeout: int = _int("MQTT_TIMEOUT", 10)
    mqtt_reconnect_min: int = _int("MQTT_RECONNECT_MIN", 1)
    mqtt_reconnect_max: int = _int("MQTT_RECONNECT_MAX", 30)

    influx_url: str = os.getenv("INFLUX_URL", "http://localhost:8086")
    influx_token: str = os.getenv("INFLUX_TOKEN", "")
    influx_org: str = os.getenv("INFLUX_ORG", "")
    influx_bucket: str = os.getenv("INFLUX_BUCKET", "")
    influx_timeout_ms: int = _int("INFLUX_TIMEOUT_MS", 10000)
    influx_batch_size: int = _int("INFLUX_BATCH_SIZE", 100)
    influx_flush_interval_ms: int = _int("INFLUX_FLUSH_INTERVAL_MS", 1000)

    pending_db: Path = ROOT / os.getenv("PENDING_DB", "pending_queue.db")
    state_db: Path = ROOT / os.getenv("STATE_DB", "system_state.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    pollution_threshold_ntu: float = _float("POLLUTION_THRESHOLD_NTU", 15.0)

    @property
    def mqtt_configured(self) -> bool:
        return bool(self.mqtt_host and 0 < self.mqtt_port < 65536 and self.mqtt_qos in (0, 1, 2))

    @property
    def influx_configured(self) -> bool:
        return bool(self.influx_url and self.influx_token and self.influx_org and self.influx_bucket)


def get_settings() -> Settings:
    return Settings()

