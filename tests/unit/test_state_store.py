from uuid import uuid4

from consumer.state_store import StateStore
from project_io import iso_now


def reading(frame=1):
    return {
        "message_id": str(uuid4()),
        "device_id": "sonda-001",
        "frame_counter": frame,
        "sent_at": iso_now(),
    }


def test_message_duplicate_and_trace(tmp_path):
    store = StateStore(tmp_path / "state.db")
    item = reading()
    assert store.first_seen(item)
    assert not store.first_seen(item)
    store.stage(item["message_id"], "validated")
    assert store.get_message(item["message_id"])["status"] == "validated"


def test_frame_order_and_gaps(tmp_path):
    store = StateStore(tmp_path / "state.db")
    assert store.frame_status("sonda", 10) == ("first", [])
    assert store.frame_status("sonda", 12) == ("gap", [11])
    assert store.frame_status("sonda", 11) == ("out_of_order", [])
    assert store.frame_status("sonda", 13) == ("ordered", [])

