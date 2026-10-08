# Plano de testes

## Critério de prova

Uma mensagem só é confirmada quando é publicada, recebida, validada, escrita, consultada por `message_id` e comparada. O end-to-end exige igualdade das contagens. Um registro ausente produz `FAIL`.

## Suítes

- `tests/unit`: parser, regras, continuidade, fila SQLite e ordem; sem serviços externos.
- `tests/integration`: MQTT, InfluxDB, fluxo completo e falhas; serviços reais.
- `tests/load`: escala, frequência e batch; execução deliberada.
- `tests/hardware`: marcado `SKIPPED` até existir LoRaWAN físico.

## Carga progressiva

```powershell
python -m tests.load.load_test --scale --messages-per-device 10
python -m tests.load.load_test --devices 100 --messages 10000
python -m tests.load.load_test --devices 500 --messages 50000
python -m tests.load.test_batch --total 1000
python -m tests.load.test_frequency --messages-per-rate 1000
```

Volumes aceitos vão até 500 mil e devices até 1000. Comece pequeno, observe CPU, memória, disco e fila, e só então avance. O teste registra gerado, publicado, recebido, validado, rejeitado, escrito, localizado, perda, duplicidade, ordem, tempo, taxa e percentis disponíveis.

O relatório deve responder com dados: “Qual foi o comportamento observado do InfluxDB e da aplicação com o aumento do volume?”. Sem execução não há resposta.

## Falhas

`python -m tests.integration.test_failures` usa uma URL deliberadamente fechada para comprovar enfileiramento. Se o InfluxDB normal estiver configurado, recupera, consulta e então remove. O teste MQTT confirma detecção de indisponibilidade; reconexão após reinício real do broker permanece `NOT TESTED` até o apresentador controlar o processo.

`python -m tests.integration.test_message_rules` publica o mesmo UUID duas vezes e envia as sequências 10–12–11 e 20–23 pelo MQTT real. O resultado exige duplicidade, fora de ordem e três frames possivelmente ausentes.

`python -m tests.integration.test_consumer_restart` grava uma mensagem, encerra o consumer, cria outra instância usando os mesmos bancos SQLite, grava a segunda e consulta ambas no InfluxDB. Sem os serviços reais o resultado é `NOT EXECUTED`.

`python -m tests.integration.test_mqtt_reconnect` controla uma segunda instância local do Mosquitto na porta 1884. O teste derruba essa instância, confirma o estado offline, restaura o broker, aguarda reconnect automático e comprova uma nova mensagem no InfluxDB.

## Network data pipeline test

Na máquina C, deixe `python -m consumer.consumer` ativo. Na máquina A:

```powershell
python -m tests.integration.network_pipeline send --messages 100 --devices 10
```

Copie o manifest indicado para a máquina C e execute:

```powershell
python -m tests.integration.network_pipeline verify --manifest caminho\manifest.json
```

O segundo comando cruza o manifest do emissor, o rastreamento do consumer e a consulta real ao InfluxDB.

Registre no relatório:

- hostname e IP do simulador;
- hostname e IP do MQTT;
- hostname e IP do consumer;
- hostname e IP do InfluxDB;
- UUID, `sent_at`, recepção no consumer, confirmação no banco e latência.

É comunicação IP real. Não a descreva como distância LoRaWAN.
