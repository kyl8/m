from __future__ import annotations

import json
import threading
import time
from typing import Any

from config import Settings
from mqtt.publisher import build_client


class MqttSubscriber:
    def __init__(self, settings: Settings, topic: str | None = None, client_id: str = "portos-subscriber"):
        self.settings = settings
        self.topic = topic or settings.mqtt_topic
        self.client = build_client(settings, client_id)
        self.connected = threading.Event()
        self.received = threading.Event()
        self.messages: list[tuple[dict[str, Any], float]] = []
        self.error: str | None = None
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            client.subscribe(self.topic, qos=self.settings.mqtt_qos)
            self.connected.set()
        else:
            self.error = str(reason_code)

    def _on_message(self, client, userdata, message) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8"))
            self.messages.append((payload, time.perf_counter()))
            self.received.set()
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self.error = str(exc)
            self.received.set()

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.connected.clear()

    def start(self) -> None:
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_timeout)
        self.client.loop_start()
        if not self.connected.wait(self.settings.mqtt_timeout):
            self.stop()
            raise TimeoutError(self.error or "timeout aguardando conexão e assinatura MQTT")

    def wait(self, timeout: float | None = None) -> tuple[dict[str, Any], float]:
        if not self.received.wait(timeout or self.settings.mqtt_timeout):
            raise TimeoutError("nenhuma mensagem recebida dentro do timeout")
        if self.error:
            raise ValueError(self.error)
        return self.messages[-1]

    def stop(self) -> None:
        if self.client.is_connected():
            self.client.disconnect()
        self.client.loop_stop()
