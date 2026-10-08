from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings
from consumer.state_store import StateStore
from mqtt.publisher import MqttPublisher, PublishError
from project_io import iso_now, latency_stats, save_artifact, save_report
from simulator.payload_factory import make_uplink
from simulator.radio_model import simulated_radio
from simulator.sensor_model import SensorState

SUPPORTED_DEVICES = (1, 10, 50, 100, 500, 1000)


def run_simulation(
    devices: int,
    messages: int,
    profile: str,
    interval: float | None,
    event: str | None,
    packet_loss: float,
    distance_m: float,
    verbose: bool,
) -> dict[str, Any]:
    if devices < 1 or devices > 1000:
        raise ValueError("devices deve estar entre 1 e 1000")
    if messages < 1 or messages > 500_000:
        raise ValueError("messages deve estar entre 1 e 500000")
    if not 0 <= packet_loss <= 0.5:
        raise ValueError("packet-loss deve estar entre 0 e 0.5")

    settings = get_settings()
    rng = random.Random()
    states = {f"sonda-{number:03d}": SensorState.create(rng) for number in range(1, devices + 1)}
    publisher = MqttPublisher(settings)
    state_store = StateStore(settings.state_db)
    latencies: list[float] = []
    generated = published = simulated_loss = 0
    delay = interval if interval is not None else (30.0 if profile == "realistic" else 0.0)
    started_at = iso_now()
    wall_start = time.perf_counter()

    print("=" * 60)
    print("PORTOS CONECTADOS - SIMULADOR")
    print("RADIO MODE: SIMULATED")
    print("PHYSICAL RANGE VALIDATION: NOT PERFORMED")
    if profile == "stress":
        print("BACKEND STRESS TEST")
        print("THIS DOES NOT REPRESENT LORAWAN AIR TRAFFIC")
    print("=" * 60)

    try:
        publisher.connect()
        for index in range(messages):
            device_id = f"sonda-{index % devices + 1:03d}"
            frame = state_store.next_simulator_frame(device_id)
            pollution = 0.0
            if event == "pollution" and device_id == "sonda-003" and index >= int(messages * 0.4):
                pollution = 6.0
            reading = states[device_id].next_reading(rng, pollution=pollution)
            radio = simulated_radio(distance_m, rng)
            payload = make_uplink(device_id, frame, reading, radio)
            generated += 1
            state_store.increment("generated")
            if rng.random() < packet_loss:
                simulated_loss += 1
                if verbose:
                    print(f"[WARNING] SIMULATED PACKET LOSS {device_id} frame={frame}")
                continue
            before = time.perf_counter()
            publisher.publish(payload)
            latencies.append((time.perf_counter() - before) * 1000)
            published += 1
            state_store.increment("published")
            if verbose:
                message_id = payload["uplink_message"]["decoded_payload"]["message_id"]
                print(f"[PASS] MQTT published {device_id} frame={frame} message={message_id}")
            elif index == 0 or index + 1 == messages or (index + 1) % max(1, messages // 10) == 0:
                print(f"[INFO] Published {index + 1}/{messages}")
            if delay:
                time.sleep(delay)
    except (PublishError, KeyboardInterrupt) as exc:
        error = str(exc)
        print(f"[ERROR] {error}")
    else:
        error = None
    finally:
        publisher.close()

    elapsed = time.perf_counter() - wall_start
    result = {
        "test": "SIMULATOR",
        "started_at": started_at,
        "finished_at": iso_now(),
        "status": "PASS" if error is None and published + simulated_loss == generated else "FAIL",
        "radio_mode": "SIMULATED",
        "physical_range_validation": "NOT PERFORMED",
        "profile": profile,
        "devices": devices,
        "generated": generated,
        "published": published,
        "simulated_packet_loss": simulated_loss,
        "elapsed_seconds": elapsed,
        "publish_messages_per_second": published / elapsed if elapsed else 0,
        **latency_stats(latencies),
    }
    if error:
        result["error"] = error
    json_path, txt_path = save_report("simulator", result)
    evidence_path = save_artifact("evidence", "simulator", result)
    result["reports"] = [str(json_path), str(txt_path)]
    result["evidence"] = str(evidence_path)
    print(f"\nGenerated: {generated} | Published: {published} | Simulated loss: {simulated_loss}")
    print(f"Rate: {result['publish_messages_per_second']:.2f} msg/s")
    print(f"Report: {json_path}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Simula sondas e publica uplinks reais no MQTT")
    parser.add_argument("--devices", type=int, default=1)
    parser.add_argument("--messages", type=int, default=100)
    parser.add_argument("--profile", choices=("realistic", "stress"), default="realistic")
    parser.add_argument("--interval", type=float, help="segundos entre mensagens; substitui o padrão do perfil")
    parser.add_argument("--event", choices=("pollution",))
    parser.add_argument("--packet-loss", type=float, default=0.0, help="perda sintética entre 0 e 0.5")
    parser.add_argument("--distance-m", type=float, default=100.0, help="metadado sintético; não mede alcance")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.event == "pollution" and args.devices < 3:
        print("[INFO] O evento usa a sonda-003; quantidade de sondas ajustada para 3.")
        args.devices = 3
    if args.event and args.interval is None:
        print("[INFO] Demonstração acelerada para uma mensagem a cada 0,2 segundo.")
        args.interval = 0.2
    run_simulation(
        args.devices, args.messages, args.profile, args.interval, args.event,
        args.packet_loss, args.distance_m, args.verbose,
    )


if __name__ == "__main__":
    main()
