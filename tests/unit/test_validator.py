from uuid import uuid4

from consumer.validator import validate_reading
from project_io import iso_now


def valid_reading():
    return {
        "device_id": "sonda-001",
        "message_id": str(uuid4()),
        "sent_at": iso_now(),
        "received_at": iso_now(),
        "source": "simulator",
        "temperature_c": 25.0,
        "ph": 7.5,
        "turbidity_ntu": 10.0,
    }


def test_accepts_valid_reading():
    result = validate_reading(valid_reading())
    assert result.valid
    assert result.errors == []


def test_rejects_required_fields_and_bad_formats():
    reading = valid_reading()
    reading.update(device_id="", message_id="not-a-uuid", sent_at="yesterday", ph="abc")
    result = validate_reading(reading)
    assert not result.valid
    assert len(result.errors) == 4


def test_rejects_nan_infinity_and_negative_turbidity():
    for field, value in (("ph", float("nan")), ("temperature_c", float("inf")), ("turbidity_ntu", -0.1)):
        reading = valid_reading()
        reading[field] = value
        assert not validate_reading(reading).valid


def test_suspicious_ph_is_warning_not_format_error():
    reading = valid_reading()
    reading["ph"] = 13.5
    result = validate_reading(reading)
    assert result.valid
    assert result.warnings


def test_absurd_temperature_is_rejected():
    reading = valid_reading()
    reading["temperature_c"] = 200
    result = validate_reading(reading)
    assert not result.valid
