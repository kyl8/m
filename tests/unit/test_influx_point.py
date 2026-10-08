from uuid import uuid4

from consumer.influx_writer import InfluxWriter
from project_io import iso_now


def test_point_uses_expected_measurement_tags_fields_and_timestamp():
    message_id = str(uuid4())
    reading = {
        "device_id": "sonda-001",
        "gateway_id": "gateway-001",
        "site": "porto-poc",
        "source": "simulator",
        "message_id": message_id,
        "sent_at": iso_now(),
        "received_at": iso_now(),
        "temperature_c": 25.123456,
        "ph": 7.654321,
        "frame_counter": 42,
    }
    line = InfluxWriter._point(reading).to_line_protocol()
    series, fields, timestamp = line.split(" ")
    assert series.startswith("water_quality,")
    assert "device_id=sonda-001" in series
    assert "gateway_id=gateway-001" in series
    assert "site=porto-poc" in series
    assert "source=simulator" in series
    assert f'message_id="{message_id}"' in fields
    assert "temperature_c=25.123456" in fields
    assert "ph=7.654321" in fields
    assert "frame_counter=42i" in fields
    assert timestamp.isdigit()

