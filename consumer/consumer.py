from __future__ import annotations

import argparse
import json
import threading
from collections import defaultdict, deque
from typing import Any

from config import Settings, get_settings
from consumer.influx_writer import InfluxUnavailable, InfluxWriter
from consumer.parser import PayloadParseError, parse_uplink
from consumer.pending_queue import PendingQueue
from consumer.state_store import StateStore
from consumer.validator import validate_reading
from mqtt.publisher import build_client
from project_io import iso_now, parse_time, utc_now


class Consumer:
    def __init__(self, settings: Settings, *, verify_writes: bool = False, verbose: bool = False):
        self.settings = settings
        self.verify_writes = verify_writes
        self.verbose = verbose
        self.queue = PendingQueue(settings.pending_db)
        self.state = StateStore(settings.state_db)
        self.influx = InfluxWriter(settings)
        self.client = build_client(settings, "portos-consumer")
        self.connected = threading.Event()
        self.stop_event = threading.Event()
        self.turbidity: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=5))
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            client.subscribe(self.settings.mqtt_topic, qos=self.settings.mqtt_qos)
            self.connected.set()
            print(f"[INFO] MQTT connected to {self.settings.mqtt_host}:{self.settings.mqtt_port}")
        else:
            print(f"[ERROR] MQTT connection refused: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.connected.clear()
        if not self.stop_event.is_set():
            print(f"[WARNING] MQTT OFFLINE - automatic retry enabled ({reason_code})")

    def _on_message(self, client, userdata, message) -> None:
        self.state.increment("received")
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            reading = parse_uplink(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, PayloadParseError) as exc:
            self.state.increment("rejected")
            print(f"[REJECTED] INVALID FORMAT: {exc}")
            return

        message_id = reading.get("message_id")
        validation = validate_reading(reading)
        if not validation.valid:
            self.state.increment("rejected")
            if isinstance(message_id, str):
                self.state.first_seen(reading)
                self.state.reject(message_id, "; ".join(validation.errors))
            print(f"[REJECTED] INVALID FORMAT: {'; '.join(validation.errors)}")
            return

        if not self.state.first_seen(reading):
            self.state.increment("duplicates")
            print(f"[WARNING] DUPLICATE DETECTED message_id={message_id}")
            return

        self.state.stage(message_id, "validated")
        self.state.increment("valid")
        latency_ms = max(0.0, (utc_now() - parse_time(reading["sent_at"])).total_seconds() * 1000)
        reading["latency_ms"] = latency_ms
        frame_status, missing = self.state.frame_status(reading["device_id"], reading.get("frame_counter"))
        if frame_status == "out_of_order":
            self.state.increment("out_of_order")
            print(f"[WARNING] OUT OF ORDER {reading['device_id']} frame={reading.get('frame_counter')}")
        elif frame_status == "gap":
            self.state.increment("possible_loss", len(missing))
            shown = missing[:20]
            suffix = "..." if len(missing) > 20 else ""
            print(f"[WARNING] POSSIBLE PACKET LOSS missing frames: {shown}{suffix}")

        for warning in validation.warnings:
            print(f"[WARNING] ENVIRONMENTAL WARNING: {warning}")
        self._check_turbidity(reading)
        if self.verbose:
            print(f"[RECEIVED] {reading['device_id']} frame={reading.get('frame_counter')} message={message_id}")
        self._store(reading)

    def _store(self, reading: dict[str, Any]) -> None:
        message_id = reading["message_id"]
        try:
            self.influx.write(reading)
            self.state.increment("written")
            self.state.stage(message_id, "written", latency_ms=reading["latency_ms"])
            if self.verbose:
                print("[PASS] InfluxDB write")
            if self.verify_writes:
                ok, _, differences = self.influx.verify(reading)
                if not ok:
                    raise InfluxUnavailable("; ".join(differences))
                self.state.increment("confirmed")
                self.state.stage(message_id, "confirmed")
                if self.verbose:
                    print("[PASS] database verification")
        except InfluxUnavailable as exc:
            queued = self.queue.put(reading, str(exc))
            if queued:
                self.state.increment("queued")
            print(f"[FAIL] INFLUXDB OFFLINE: {exc}")
            print(f"[INFO] Message saved to local pending queue. Pending: {self.queue.count()}")

    def _check_turbidity(self, reading: dict[str, Any]) -> None:
        value = reading.get("turbidity_ntu")
        if not isinstance(value, (int, float)):
            return
        history = self.turbidity[reading["device_id"]]
        previous = sum(history) / len(history) if history else value
        history.append(float(value))
        if len(history) >= 3 and value - previous >= self.settings.pollution_threshold_ntu:
            self.state.increment("environmental_events")
            print("[ENVIRONMENTAL EVENT]")
            print(f"Device: {reading['device_id']}")
            print(f"Turbidity change detected. Previous average: {previous:.2f}; Current: {value:.2f}")
            print("[INFO] Alteração detectada; isto não confirma poluição real.")

    def recover_pending(self, limit: int = 1000) -> tuple[int, int]:
        total = self.queue.count()
        recovered = 0
        if not total:
            return 0, 0
        print("[INFO] Reprocessing pending messages...")
        for item in self.queue.items(limit):
            try:
                self.influx.write(item["reading"])
                ok, _, differences = self.influx.verify(item["reading"])
                if not ok:
                    raise InfluxUnavailable("; ".join(differences))
                self.queue.remove(item["message_id"])
                self.state.increment("recovered")
                current = self.state.get_message(item["message_id"])
                if not current or not current.get("written_at"):
                    self.state.increment("written")
                    self.state.stage(item["message_id"], "written")
                self.state.increment("confirmed")
                self.state.stage(item["message_id"], "confirmed")
                recovered += 1
            except InfluxUnavailable as exc:
                self.queue.mark_attempt(item["message_id"], str(exc))
                break
        print(f"[INFO] {recovered}/{total} pending messages confirmed in InfluxDB")
        return recovered, total

    def start(self) -> None:
        print("RADIO MODE: SIMULATED OR EXTERNAL UPLINK")
        print("PHYSICAL RANGE VALIDATION: NOT PERFORMED")
        self.state.set_meta("consumer_status", "RUNNING")
        self.state.set_meta("consumer_heartbeat", iso_now())
        self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_timeout)
        self.client.loop_start()

    def stop(self) -> None:
        self.stop_event.set()
        self.state.set_meta("consumer_status", "STOPPED")
        if self.client.is_connected():
            self.client.disconnect()
        self.client.loop_stop()
        self.influx.close()

    def run_forever(self) -> None:
        self.start()
        try:
            while not self.stop_event.wait(5):
                self.state.set_meta("consumer_heartbeat", iso_now())
                if self.queue.count():
                    self.recover_pending()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Consumer MQTT do Portos Conectados")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--verify-writes", action="store_true", help="consulta cada mensagem após gravar; reduz throughput")
    args = parser.parse_args()
    Consumer(get_settings(), verify_writes=args.verify_writes, verbose=args.verbose).run_forever()


if __name__ == "__main__":
    main()
