import pytest


@pytest.mark.hardware
def test_real_lorawan_radio_range():
    pytest.skip("SKIPPED: requer dispositivo, gateway e Network Server LoRaWAN físicos")

