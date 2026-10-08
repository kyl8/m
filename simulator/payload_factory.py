from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def make_uplink(
    device_id: str,
    frame_counter: int,
    reading: dict[str, float],
    radio: dict[str, Any],
    *,
    site: str = "porto-poc",
    source: str = "simulator",
    sent_at: str | None = None,
    message_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    decoded = {
        "message_id": message_id or str(uuid4()),
        "sent_at": sent_at or now,
        "site": site,
        "source": source,
        **reading,
    }
    if "distance_m" in radio:
        decoded["distance_m"] = radio["distance_m"]
    return {
        "end_device_ids": {"device_id": device_id},
        "received_at": now,
        "uplink_message": {
            "f_cnt": frame_counter,
            "decoded_payload": decoded,
            "rx_metadata": [{
                "gateway_ids": {"gateway_id": "gateway-simulado-001"},
                "rssi": radio.get("rssi"),
                "snr": radio.get("snr"),
            }],
            "settings": {
                "frequency": str(radio.get("frequency_hz", 915_000_000)),
                "data_rate": {
                    "lora": {
                        "spreading_factor": radio.get("spreading_factor", 7),
                        "bandwidth": radio.get("bandwidth_hz", 125_000),
                    }
                },
            },
        },
    }
