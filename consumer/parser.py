from __future__ import annotations

from typing import Any


class PayloadParseError(ValueError):
    pass


def parse_uplink(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        device_id = payload["end_device_ids"]["device_id"]
        received_at = payload["received_at"]
        uplink = payload["uplink_message"]
        decoded = uplink["decoded_payload"]
    except (KeyError, TypeError) as exc:
        raise PayloadParseError(f"estrutura de uplink incompleta: {exc}") from exc

    metadata = uplink.get("rx_metadata") or []
    # O The Things Stack pode enviar vários gateways. Usamos o sinal RSSI mais forte.
    strongest = max(metadata, key=lambda item: item.get("rssi", -999), default={})
    gateway_id = strongest.get("gateway_ids", {}).get("gateway_id", "unknown")
    lora = uplink.get("settings", {}).get("data_rate", {}).get("lora", {})

    return {
        "device_id": device_id,
        "message_id": decoded.get("message_id"),
        "frame_counter": uplink.get("f_cnt"),
        "site": decoded.get("site", "unknown"),
        "sent_at": decoded.get("sent_at"),
        "received_at": received_at,
        "source": decoded.get("source"),
        "temperature_c": decoded.get("temperature_c"),
        "ph": decoded.get("ph"),
        "turbidity_ntu": decoded.get("turbidity_ntu"),
        "conductivity_us_cm": decoded.get("conductivity_us_cm"),
        "dissolved_oxygen_mg_l": decoded.get("dissolved_oxygen_mg_l"),
        "gateway_id": gateway_id,
        "rssi_dbm": strongest.get("rssi"),
        "snr_db": strongest.get("snr"),
        "frequency_hz": _number(uplink.get("settings", {}).get("frequency")),
        "spreading_factor": lora.get("spreading_factor"),
        "bandwidth_hz": lora.get("bandwidth"),
        "distance_m": decoded.get("distance_m"),
    }


def _number(value: Any) -> int | float | None:
    if value is None:
        return None
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return value

