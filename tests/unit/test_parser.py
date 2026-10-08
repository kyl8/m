from consumer.parser import PayloadParseError, parse_uplink
from simulator.payload_factory import make_uplink


def sample_payload():
    return make_uplink(
        "sonda-007",
        42,
        {"temperature_c": 25.1, "ph": 7.4, "turbidity_ntu": 12.0},
        {
            "rssi": -88,
            "snr": 6.2,
            "distance_m": 100,
            "frequency_hz": 915_000_000,
            "spreading_factor": 7,
            "bandwidth_hz": 125_000,
        },
    )


def test_parse_uplink_flattens_network_server_payload():
    reading = parse_uplink(sample_payload())
    assert reading["device_id"] == "sonda-007"
    assert reading["frame_counter"] == 42
    assert reading["gateway_id"] == "gateway-simulado-001"
    assert reading["temperature_c"] == 25.1
    assert reading["source"] == "simulator"


def test_parser_uses_strongest_gateway():
    payload = sample_payload()
    payload["uplink_message"]["rx_metadata"].append(
        {"gateway_ids": {"gateway_id": "gateway-strong"}, "rssi": -70, "snr": 8}
    )
    reading = parse_uplink(payload)
    assert reading["gateway_id"] == "gateway-strong"
    assert reading["rssi_dbm"] == -70


def test_parser_rejects_missing_structure():
    try:
        parse_uplink({"end_device_ids": {}})
    except PayloadParseError:
        pass
    else:
        raise AssertionError("payload incompleto deveria falhar")

