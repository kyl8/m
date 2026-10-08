# Requisitos dos dados

## Campos

| Nome interno | Exibição | Tipo | Unidade | Obrigatório | Armazenamento / regra |
|---|---|---:|---|---|---|
| `device_id` | Sonda | texto | — | sim | tag; não vazio |
| `message_id` | Mensagem | UUID | — | sim | field; UUID válido e controle local de duplicidade |
| `frame_counter` | Contador | inteiro | frame | recomendado | field; lacunas e retrocessos são sinalizados |
| `gateway_id` | Gateway | texto | — | não | tag |
| `site` | Local | texto | — | não | tag de baixa cardinalidade |
| `source` | Origem | enum | — | sim | tag; `simulator` ou `lorawan-real` |
| `sent_at` | Gerada em | ISO 8601 | UTC | sim | field; exige timezone |
| `received_at` | Recebida em | ISO 8601 | UTC | sim nesta integração | timestamp do ponto no InfluxDB |
| `temperature_c` | Temperatura | float | °C | não | field; -20 a 80 aceita pela POC; fora rejeita; -5 a 50 gera alerta |
| `ph` | pH | float | escala pH | não | field; 0 a 14; abaixo de 5 ou acima de 10 gera alerta contextual |
| `turbidity_ntu` | Turbidez | float | NTU | não | field; negativo rejeita |
| `conductivity_us_cm` | Condutividade | float | µS/cm | não | field; negativo rejeita |
| `dissolved_oxygen_mg_l` | Oxigênio dissolvido | float | mg/L | não | field; negativo rejeita |
| `rssi_dbm` | RSSI | float | dBm | não | field; simulado nesta etapa |
| `snr_db` | SNR | float | dB | não | field; simulado nesta etapa |
| `distance_m` | Distância | float | m | não | field; simulado nesta etapa |

Os limites ambientais são regras operacionais da POC, não critérios legais de qualidade da água. pH 13,5, por exemplo, é número válido e produz `ENVIRONMENTAL WARNING`; `"abc"` é `INVALID FORMAT`.

## Tempo e precisão

Todos os timestamps usam ISO 8601 com timezone e são normalizados em UTC. `sent_at` vem da sonda ou simulador; `received_at` vem do envelope do Network Server. O InfluxDB usa `received_at` como tempo do ponto e precisão de nanossegundos na API. A precisão real nunca é maior que a do relógio de origem.

`latency_ms` é calculada entre `sent_at` e o relógio do consumer. Entre máquinas, sincronização de relógios é requisito. A confirmação do banco possui horário separado no rastreamento.

## Ausência, inválidos e repetição

Variáveis ambientais são opcionais porque sondas futuras podem ter conjuntos de sensores diferentes. Campo ausente não vira zero. `NaN`, `Infinity`, booleanos no lugar de números e unidades não acordadas são rejeitados.

`message_id` identifica uma mensagem globalmente. O SQLite do consumer impede novo processamento do mesmo UUID. `frame_counter` detecta provável lacuna ou chegada fora de ordem, mas sozinho não prova perda no rádio. Mensagens atrasadas preservam `sent_at` e são gravadas com `received_at` do uplink.

No InfluxDB, um ponto é identificado por measurement, conjunto de tags e timestamp. Dois pontos com essa identidade podem ser mesclados. Por isso o emissor deve fornecer timestamp suficientemente preciso e o consumer mantém deduplicação por UUID. `message_id` fica como field para evitar uma série nova por mensagem.

