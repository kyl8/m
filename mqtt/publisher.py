from __future__ import annotations

import json
import threading
from typing import Any

import paho.mqtt.client as mqtt

from config import Settings


class PublishError(RuntimeError):
    pass


def build_client(settings: Settings, client_id: str = "") -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    client.reconnect_delay_set(settings.mqtt_reconnect_min, settings.mqtt_reconnect_max)
    return client


class MqttPublisher:
    def __init__(self, settings: Settings, client_id: str = "portos-simulator"):
        self.settings = settings
        self.client = build_client(settings, client_id)
        self.connected = threading.Event()
        self.connect_error: str | None = None
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            self.connect_error = None
            self.connected.set()
        else:
            self.connect_error = str(reason_code)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self.connected.clear()

    def connect(self) -> None:
        try:
            self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, self.settings.mqtt_timeout)
            self.client.loop_start()
        except OSError as exc:
            raise PublishError(f"não foi possível conectar ao MQTT: {exc}") from exc
        if not self.connected.wait(self.settings.mqtt_timeout):
            self.client.loop_stop()
            raise PublishError(self.connect_error or "timeout aguardando conexão MQTT")

    def publish(self, payload: dict[str, Any], topic: str | None = None) -> None:
        if not self.connected.is_set():
            raise PublishError("MQTT OFFLINE")
        info = self.client.publish(
            topic or self.settings.mqtt_topic,
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            qos=self.settings.mqtt_qos,
        )
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise PublishError(mqtt.error_string(info.rc))
        try:
            info.wait_for_publish(timeout=self.settings.mqtt_timeout)
        except RuntimeError as exc:
            raise PublishError(str(exc)) from exc
        if not info.is_published():
            raise PublishError("broker não confirmou a publicação dentro do timeout")

    def close(self) -> None:
        if self.client.is_connected():
            self.client.disconnect()
        self.client.loop_stop()


def publish_once(payload: dict[str, Any], settings: Settings, topic: str | None = None) -> None:
    publisher = MqttPublisher(settings, client_id="portos-publish-once")
    try:
        publisher.connect()
        publisher.publish(payload, topic)
    finally:
        publisher.close()

