# Guia de apresentação

## Ideia em uma frase

Esta bancada verifica se uma medição sai de uma sonda simulada, atravessa um entregador de mensagens e reaparece no banco com o mesmo identificador e os mesmos valores.

## Quem faz o quê

- **Sonda:** é quem mede.
- **LoRaWAN:** será o caminho sem fio usado pela sonda física.
- **Gateway:** será a ponte entre o rádio e a Internet.
- **MQTT:** é o sistema de entrega de mensagens.
- **Consumer:** abre, confere e interpreta cada mensagem.
- **InfluxDB:** guarda as medições organizadas pelo tempo.

Nesta etapa, a sonda e as condições de rádio são simuladas. MQTT, comunicação TCP/IP, consumer, gravação e consulta ao InfluxDB são reais.

## Antes da apresentação

1. Inicie Mosquitto e InfluxDB.
2. Confira o `.env`.
3. Execute `scripts\check_environment.bat`.
4. Execute uma vez `scripts\test_end_to_end.bat`.
5. Não apague evidências que pretende mostrar.

## Demonstração

Execute:

```text
scripts\demo.bat
```

Roteiro sugerido:

1. **Verificar ambiente:** mostra os serviços disponíveis e a versão detectada.
2. **Testar MQTT:** envia um UUID e exige o mesmo UUID no subscriber.
3. **Testar InfluxDB:** grava dois números com precisão conhecida, consulta e compara.
4. **Testar fluxo completo:** usa 100 mensagens e falha se uma não for localizada.
5. **Rastrear uma mensagem:** copie um `message_id` exibido e mostre cada etapa registrada.
6. **Simular 10 sondas:** cada uma mantém estado e contador próprios.
7. **Teste de grande volume:** explique o aviso de que não é tráfego de rádio.
8. **Mensagem inválida:** pH textual precisa ser rejeitado.
9. **Recuperação:** uma URL de banco indisponível envia a leitura à fila SQLite.
10. **Estatísticas:** mostre contadores sem esconder rejeições ou perdas.

## Três experimentos, três conclusões

**Teste 1 — software local**

Comprova lógica, MQTT, consumer, banco, consulta e integridade dos valores.

**Teste 2 — rede entre computadores**

Comprova transmissão TCP/IP real entre máquinas. Não comprova rádio nem distância LoRaWAN.

**Teste 3 — LoRaWAN físico**

Com dispositivo, gateway e Network Server reais, poderá comprovar rádio, PDR, RSSI, SNR e alcance nas condições do ensaio.

## Como falar dos resultados

- **Measured / medido:** horários capturados, quantidade recebida, latência.
- **Calculated / calculado:** média, percentis, throughput e perda derivados das medições.
- **Simulated / simulado:** distância, RSSI e SNR produzidos pelo modelo.
- **Not tested / não testado:** alcance físico LoRaWAN enquanto não houver hardware.

Se um serviço não estava disponível, diga “não executado nesta etapa”. Não transforme `SKIPPED` ou `NOT EXECUTED` em sucesso.

