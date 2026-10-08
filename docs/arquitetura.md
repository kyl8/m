# Arquitetura

## Fluxo implementado

```text
simulator/payload_factory.py
          |
          | MQTT QoS configurável, TCP/IP real
          v
Eclipse Mosquitto
          |
          v
consumer/consumer.py
    | parser -> validação -> duplicidade/ordem
    |                    |
    |                    +-> SQLite se InfluxDB estiver indisponível
    v
InfluxDB 2.x / water_quality
          |
          v
consulta por message_id + comparação
```

O payload se aproxima do uplink decodificado do The Things Stack. O parser está isolado para que uma integração ChirpStack ou outra versão do Network Server altere esse ponto, não o restante do consumer.

## Limites experimentais

| Experimento | Comprova | Não comprova |
|---|---|---|
| Software local | processamento, MQTT, gravação, consulta, latência e perda | alcance de rádio |
| Máquinas em LAN | tráfego TCP/IP real entre hosts | LoRaWAN físico |
| Campo LoRaWAN futuro | rádio, gateway, PDR, RSSI, SNR e alcance nas condições medidas | desempenho em outros locais sem novo ensaio |

Metadados `distance_m`, `rssi_dbm`, `snr_db` e perda gerados pelo simulador exercitam o software. São classificados como **SIMULATED RADIO CONDITIONS**.

## Distribuição em rede

- Máquina A: `.env` aponta `MQTT_HOST` para B; executa `python -m simulator.simulator`.
- Máquina B: Mosquitto escuta no IP da LAN, porta e autenticação configurados.
- Máquina C: consumer aponta para B; `INFLUX_URL` aponta para C ou D.
- Máquina D, opcional: InfluxDB aceita conexões autorizadas da máquina C.

Registre hostname/IP, relógio sincronizado, firewall e horários. Latência ponta a ponta só é comparável entre máquinas quando seus relógios estão sincronizados, idealmente por NTP.

