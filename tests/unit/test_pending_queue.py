from consumer.pending_queue import PendingQueue


def test_pending_queue_persists_and_deduplicates(tmp_path):
    path = tmp_path / "pending.db"
    queue = PendingQueue(path)
    reading = {"message_id": "abc", "temperature_c": 25.0}
    assert queue.put(reading, "offline")
    assert not queue.put(reading, "offline again")
    assert queue.count() == 1

    reopened = PendingQueue(path)
    item = next(reopened.items())
    assert item["reading"] == reading
    reopened.remove("abc")
    assert reopened.count() == 0

