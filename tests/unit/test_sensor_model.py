import random

from simulator.sensor_model import SensorState


def test_sensor_values_change_gradually():
    rng = random.Random(123)
    state = SensorState.create(rng)
    first = state.next_reading(rng)
    second = state.next_reading(rng)
    assert abs(second["temperature_c"] - first["temperature_c"]) < 0.5
    assert abs(second["ph"] - first["ph"]) < 0.2
    assert abs(second["conductivity_us_cm"] - first["conductivity_us_cm"]) < 1000


def test_pollution_event_increases_turbidity_progressively():
    rng = random.Random(456)
    state = SensorState.create(rng)
    before = state.turbidity_ntu
    for _ in range(5):
        reading = state.next_reading(rng, pollution=4.0)
    assert reading["turbidity_ntu"] > before + 15

