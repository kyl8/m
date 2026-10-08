# InfluxDB aplicado ao Portos Conectados

## Versão usada

O código consulta `GET /health` e imprime `InfluxDB detected version: X`. O writer atual implementa cliente, token, organização, bucket, escrita e Flux da linha 2.x. Versões 1.x e 3.x não são tratadas como equivalentes: exigem outro adaptador e outra documentação de consulta.

## Requisitos antes de escrever

1. **URL:** host e porta acessíveis ao consumer.
2. **Autenticação:** token com permissão de escrita e consulta no bucket escolhido.
3. **Organização e bucket:** `INFLUX_ORG` e `INFLUX_BUCKET`; “database” pertence a outros modos/versões.
4. **Measurement:** `water_quality`.
5. **Tags:** `device_id`, `gateway_id`, `site`, `source`. Servem para filtros frequentes e têm cardinalidade controlável.
6. **Fields:** variáveis ambientais, rádio, latência, contador, `message_id` e `sent_at`.
7. **Timestamp:** `received_at`, com `WritePrecision.NS`.
8. **Tipos:** manter o tipo de cada field estável. Não enviar texto onde já existe float.
9. **Retenção:** definir no bucket conforme objetivo acadêmico e espaço em disco; a POC não escolhe prazo sem requisito.
10. **Cardinalidade:** `message_id` não é tag porque cada UUID criaria nova série. Crescimento de devices, sites e gateways deve ser medido.
11. **Volume e frequência:** devem vir dos ensaios progressivos, não de suposição.
12. **Lotes:** `tests.load.test_batch` compara 1, 10, 100, 500 e 1000 na máquina real.
13. **Timeout/retry:** timeout vem do `.env`; falha envia o dado à fila persistente.
14. **Consulta:** o teste usa Flux, faz `pivot`, filtra `message_id` e compara fields.
15. **Duplicidade:** SQLite bloqueia UUID repetido antes da escrita. A identidade nativa do ponto ainda depende de tags e timestamp.

## Escrita individual e em lote

O consumer usa escrita síncrona individual para tornar clara a etapa de aceitação e permitir fila por mensagem. O benchmark usa listas de pontos em uma chamada para medir lotes. A melhor configuração deve ser extraída do relatório produzido localmente; não existe resultado pré-preenchido.

## Tempos diferentes

`sent_at` representa o relógio da sonda. `received_at` representa a recepção informada pelo Network Server e é o eixo temporal do banco. O horário `written_at` pertence ao rastreamento local e não substitui nenhum dos dois.

## Alta frequência e muitos dispositivos

Maior frequência aumenta chamadas, lotes pendentes e uso de disco. Mais dispositivos elevam cardinalidade pela tag `device_id`. Os testes registram throughput, percentis, fila, erros, perdas e quantidade realmente encontrada. Só esses resultados permitem descrever o comportamento da instalação usada.

