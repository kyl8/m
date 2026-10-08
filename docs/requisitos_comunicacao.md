# Requisitos da comunicação

## Contrato mínimo

Cada uplink precisa ter `device_id`, UUID `message_id`, `sent_at` com timezone e `source`. `frame_counter` é recomendado para observar lacunas e ordem. O tamanho do payload deve ser medido antes do hardware: o JSON MQTT não é o payload binário que viajará pelo rádio LoRaWAN.

## MQTT

- host, porta, tópico, usuário e senha vêm do `.env`;
- QoS aceita 0, 1 ou 2; o padrão da bancada é 1;
- timeout e atrasos mínimo/máximo de reconnect são configuráveis;
- QoS 1 pode entregar repetido, então `message_id` continua obrigatório;
- autenticação e TLS devem ser configurados antes de expor o broker fora de uma LAN controlada;
- credenciais nunca entram no repositório.

O publisher só conta `published` depois da confirmação correspondente ao QoS. O consumer registra desconexão e usa reconnect automático do cliente. Um broker offline não deve derrubar permanentemente o processo.

## Falhas e ordem

- UUID já visto: `DUPLICATE DETECTED`, sem nova escrita;
- contador menor ou igual ao último: `OUT OF ORDER`;
- salto no contador: `POSSIBLE PACKET LOSS`, com frames esperados;
- InfluxDB offline: mensagem válida vai para `pending_queue.db`;
- banco recuperado: escreve cada pendência, consulta pelo UUID e só então remove da fila;
- MQTT offline: publisher informa falha e consumer permanece em reconnect;
- logs usam `INFO`, `PASS`, `WARNING`, `ERROR` e `REJECTED`.

Intervalo e frequência dependem de consumo energético, regulamentação, capacidade da rede e necessidade ambiental. O perfil realista da POC aceita 30 ou 60 segundos; isso não prescreve a frequência final LoRaWAN. O perfil stress testa somente backend.

## Network Server futuro

The Things Stack e ChirpStack entregam uplinks via MQTT, mas tópicos, autenticação e formato do envelope variam. A integração futura deve:

1. configurar credenciais e tópico do Application Server;
2. implementar ou ajustar somente `consumer/parser.py`;
3. manter o contrato interno documentado;
4. marcar `source=lorawan-real`;
5. guardar metadados reais do gateway sem misturá-los aos simulados.

## Teste em LAN

Use IPs reais no `.env`, libere apenas as portas necessárias e sincronize relógios. O relatório precisa registrar hosts do simulador, MQTT, consumer e InfluxDB, além de `message_id`, horários e latência. O nome correto é **NETWORK DATA PIPELINE TEST**.

