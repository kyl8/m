# MQTT na bancada

MQTT entrega o uplink do Network Server ao consumer. Nesta POC o Mosquitto é um processo instalado diretamente, e a comunicação ocorre por TCP/IP real mesmo quando os processos estão na mesma máquina.

O teste básico cria um UUID, inicia subscriber independente, assina um tópico de teste, publica e compara o UUID recebido. Latência é medida pelo relógio monotônico do mesmo processo. Conexão sem recebimento não é `PASS`.

QoS 0 não confirma entrega; QoS 1 pode repetir; QoS 2 acrescenta tráfego para “exatamente uma vez” na sessão MQTT. A aplicação mantém deduplicação por UUID em qualquer QoS. O broker deve usar autenticação e, quando a rede exigir, TLS e regras de tópico.

Variáveis: `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `MQTT_TOPIC`, `MQTT_QOS`, `MQTT_TIMEOUT`, `MQTT_RECONNECT_MIN`, `MQTT_RECONNECT_MAX`.

