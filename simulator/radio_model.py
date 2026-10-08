from __future__ import annotations

import math
import random


def simulated_radio(distance_m: float, rng: random.Random) -> dict[str, float | int]:
    # RSSI e SNR são sintéticos. Estes valores não validam alcance físico LoRaWAN.
    distance = max(distance_m, 1.0)
    rssi = -45.0 - 20.0 * math.log10(distance / 10.0) + rng.gauss(0, 3.0)
    snr = 9.5 - 4.0 * math.log10(distance / 100.0) + rng.gauss(0, 1.2)
    return {
        "rssi": round(max(-125.0, min(-35.0, rssi)), 1),
        "snr": round(max(-20.0, min(12.0, snr)), 1),
        "distance_m": round(distance, 1),
        "frequency_hz": 915_000_000,
        "spreading_factor": 7,
        "bandwidth_hz": 125_000,
    }

