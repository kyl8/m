from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class SensorState:
    temperature_c: float
    ph: float
    turbidity_ntu: float
    conductivity_us_cm: float
    dissolved_oxygen_mg_l: float

    @classmethod
    def create(cls, rng: random.Random) -> SensorState:
        return cls(
            temperature_c=rng.uniform(22.0, 27.0),
            ph=rng.uniform(6.8, 8.1),
            turbidity_ntu=rng.uniform(8.0, 24.0),
            conductivity_us_cm=rng.uniform(38_000, 52_000),
            dissolved_oxygen_mg_l=rng.uniform(5.5, 8.5),
        )

    def next_reading(self, rng: random.Random, pollution: float = 0.0) -> dict[str, float]:
        self.temperature_c = _move(self.temperature_c, rng, 0.08, 22.0, 32.0)
        self.ph = _move(self.ph, rng, 0.025, 6.3, 8.8)
        self.turbidity_ntu = _move(self.turbidity_ntu, rng, 0.5, 0.1, 250.0)
        self.conductivity_us_cm = _move(self.conductivity_us_cm, rng, 180.0, 20_000, 75_000)
        self.dissolved_oxygen_mg_l = _move(self.dissolved_oxygen_mg_l, rng, 0.06, 2.0, 14.0)
        if pollution:
            self.turbidity_ntu = min(250.0, self.turbidity_ntu + pollution)
        return {
            "temperature_c": round(self.temperature_c, 4),
            "ph": round(self.ph, 4),
            "turbidity_ntu": round(self.turbidity_ntu, 4),
            "conductivity_us_cm": round(self.conductivity_us_cm, 4),
            "dissolved_oxygen_mg_l": round(self.dissolved_oxygen_mg_l, 4),
        }


def _move(value: float, rng: random.Random, step: float, minimum: float, maximum: float) -> float:
    drift = rng.gauss(0, step)
    return min(max(value + drift, minimum), maximum)

