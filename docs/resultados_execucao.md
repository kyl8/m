# Resultados validados nesta máquina

Data: 8 de outubro de 2026  
Ambiente: Windows, Python 3.14.6, Eclipse Mosquitto 2.1.2 e InfluxDB OSS 2.9.1

## Critério de aprovação

Uma mensagem só foi considerada armazenada quando percorreu MQTT, consumer e InfluxDB, foi consultada por `message_id` e teve seus valores comparados. Um retorno de escrita sem a consulta posterior não foi contado como confirmação.

## Execuções

| Verificação | Resultado observado |
|---|---|
| Suite pytest completa com integrações | 20 PASSED, 2 SKIPPED em 9,69 s |
| Teste MQTT isolado | PASS; UUID enviado e recebido; 19,884 ms |
| Teste InfluxDB isolado | PASS; 25,123456 °C e pH 7,654321 recuperados sem diferença |
| End-to-end, 100 mensagens | PASS; 100/100 confirmadas; perda 0; 20,259 msg/s; P95 2.217,452 ms |
| End-to-end, 1.000 mensagens e 10 sondas | PASS; 1.000/1.000 confirmadas; perda 0; 17,983 msg/s; P95 28.989,733 ms |
| Escala, 1 a 500 sondas | PASS em todas as cinco execuções; uma mensagem por sonda; perda 0 |
| Batch, 1.000 pontos por configuração | PASS; todos os lotes localizaram 1.000/1.000 pontos |
| Frequência, 1 a 1.000 msg/s solicitadas | PASS para as amostras de 20; vazão observada saturou em aproximadamente 18,7 msg/s |
| Duplicidade e ordem | PASS; 1 duplicata, 1 fora de ordem e 3 lacunas detectadas conforme esperado |
| InfluxDB indisponível e recuperação | PASS; leitura persistida no SQLite, reenviada, consultada e removida da fila |
| MQTT indisponível e reconexão | PASS; queda real em broker de teste, consumer permaneceu ativo, reconectou e confirmou no banco |
| Reinício do consumer | PASS; registros antes e depois do reinício confirmados; fila pendente 0 |
| Evento ambiental simulado | PASS; 60/60 mensagens recebidas e 9 alterações detectadas |
| Hardware LoRaWAN | SKIPPED; rádio e gateway físicos não estavam disponíveis |
| Carga automática no pytest | SKIPPED por segurança; as execuções manuais de carga estão registradas separadamente |

`SKIPPED` não foi tratado como `PASS`.

## Escala observada

| Sondas | Mensagens | Confirmadas | Perda | Vazão (msg/s) | Média (ms) | P95 (ms) |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1 | 1 | 0 | 4,583 | 17,432 | 17,432 |
| 10 | 10 | 10 | 0 | 16,542 | 172,858 | 244,340 |
| 50 | 50 | 50 | 0 | 19,232 | 777,284 | 1.216,231 |
| 100 | 100 | 100 | 0 | 19,803 | 1.319,238 | 2.121,202 |
| 500 | 500 | 500 | 0 | 20,149 | 6.844,378 | 11.723,254 |

O aumento de sondas elevou a fila e a latência, enquanto a vazão se aproximou de 20 mensagens por segundo. Como cada sonda enviou apenas uma mensagem, esta execução mede uma rajada crescente; não caracteriza a capacidade final sob carga sustentada.

## Lotes do InfluxDB

| Batch | Confirmadas | Erros | Vazão (pontos/s) | Tempo total (s) | Média por chamada (ms) |
|---:|---:|---:|---:|---:|---:|
| 1 | 1.000 | 0 | 420,639 | 2,377 | 2,377 |
| 10 | 1.000 | 0 | 5.917,583 | 0,169 | 1,689 |
| 100 | 1.000 | 0 | 16.124,481 | 0,062 | 6,200 |
| 500 | 1.000 | 0 | 21.903,694 | 0,046 | 22,825 |
| 1.000 | 1.000 | 0 | 22.669,311 | 0,044 | 44,109 |

O lote 1.000 apresentou a maior vazão desta execução. O lote 10 teve a menor duração média de chamada. Isso mostra um compromisso entre vazão agregada e tempo de uma chamada; não autoriza afirmar que 1.000 será sempre a melhor configuração em outra máquina ou em carga contínua.

## Respostas às perguntas do projeto

1. **O InfluxDB recebeu corretamente?** Sim, nas execuções descritas; todas as mensagens contabilizadas como confirmadas foram localizadas por consulta.
2. **Os valores foram recuperados sem alteração?** Sim, inclusive no teste controlado com 25,123456 °C e pH 7,654321.
3. **Qual latência foi observada?** No end-to-end final de 100 mensagens, média 1.423,200 ms e P95 2.217,452 ms. No teste de 1.000 mensagens, média 17.566,275 ms e P95 28.989,733 ms.
4. **Qual throughput foi observado?** 20,259 msg/s com 100 mensagens e 17,983 msg/s com 1.000 mensagens no fluxo completo. A escrita direta em lote chegou a 22.669,311 pontos/s no lote 1.000.
5. **Houve perda?** Não nessas execuções controladas.
6. **Houve duplicidade?** Não nos testes de carga; a duplicata proposital foi detectada e descartada.
7. **Mais dispositivos?** A latência cresceu, com vazão estabilizada perto de 20 msg/s na rajada medida.
8. **Mais mensagens?** A fila aumentou e a latência P95 passou de cerca de 2,2 s para 29,0 s entre os testes de 100 e 1.000 mensagens.
9. **Melhor batch?** Para vazão nesta execução, 1.000. Para menor duração média por chamada, 10. A escolha depende do objetivo operacional.
10. **InfluxDB indisponível?** A mensagem foi mantida na fila SQLite.
11. **MQTT indisponível?** O consumer detectou a queda, não encerrou e reconectou após o retorno do broker.
12. **A fila recuperou os dados?** Sim; a pendência foi escrita, consultada e removida somente após confirmação.
13. **Requisitos mínimos dos dados?** `device_id`, UUID `message_id`, `sent_at` com timezone e `source`; `frame_counter` é recomendado.
14. **Requisitos mínimos da comunicação?** Host, porta, tópico, QoS, timeout, reconexão, credenciais, contador, timestamps e persistência local.
15. **O que ainda precisa de hardware LoRaWAN?** Alcance, PDR, RSSI, SNR, configuração regional, consumo energético e comportamento de campo.

## Limitações

- Os ensaios foram realizados em uma única máquina; o experimento distribuído em três computadores não foi executado.
- O teste de rede registrado usa TCP/IP real no host local e não mede uma LAN entre máquinas.
- RSSI, SNR e distância do simulador são sintéticos.
- Não foram executadas 10.000, 50.000, 100.000 ou 500.000 mensagens nesta rodada.
- Os resultados descrevem este hardware, esta configuração e este instante; não constituem benchmark universal.
- Alcance LoRaWAN real não foi testado.

Os arquivos consolidados para auditoria estão em `results/`; os arquivos brutos continuam sendo gerados em `evidence/` e `reports/` durante cada nova execução.
