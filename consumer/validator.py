from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

ENV_FIELDS = (
    "temperature_c",
    "ph",
    "turbidity_ntu",
    "conductivity_us_cm",
    "dissolved_oxygen_mg_l",
)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_reading(reading: dict[str, Any]) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(reading.get("device_id"), str) or not reading["device_id"].strip():
        errors.append("device_id ausente ou vazio")
    try:
        UUID(str(reading.get("message_id")))
    except (ValueError, TypeError, AttributeError):
        errors.append("message_id não é um UUID válido")

    for name in ("sent_at", "received_at"):
        if not _valid_timestamp(reading.get(name)):
            errors.append(f"{name} inválido; use ISO 8601 com timezone")

    if reading.get("source") not in {"simulator", "lorawan-real"}:
        errors.append("source deve ser simulator ou lorawan-real")

    for name in ENV_FIELDS:
        value = reading.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{name}: formato inválido, esperado número")
        elif not math.isfinite(value):
            errors.append(f"{name}: NaN e Infinity não são aceitos")

    _validate_ranges(reading, errors, warnings)
    return ValidationResult(not errors, errors, warnings)


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def _validate_ranges(reading: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    ph = reading.get("ph")
    if _finite_number(ph):
        if ph < 0 or ph > 14:
            errors.append("ph fora da escala numérica 0–14")
        elif ph < 5 or ph > 10:
            warnings.append("ph ambiental suspeito para o contexto da POC")

    turbidity = reading.get("turbidity_ntu")
    if _finite_number(turbidity) and turbidity < 0:
        errors.append("turbidity_ntu não pode ser negativa")

    for name in ("conductivity_us_cm", "dissolved_oxygen_mg_l", "distance_m"):
        value = reading.get(name)
        if _finite_number(value) and value < 0:
            errors.append(f"{name} não pode ser negativo")

    temperature = reading.get("temperature_c")
    if _finite_number(temperature):
        if temperature < -20 or temperature > 80:
            errors.append("temperature_c fora do limite operacional da POC (-20 a 80 °C)")
        elif temperature < -5 or temperature > 50:
            warnings.append("temperature_c ambiental suspeita; revisar sensor e contexto")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

