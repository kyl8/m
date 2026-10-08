# LoRaWAN: posição futura na arquitetura

**LoRa** é a camada de rádio. **LoRaWAN** define comunicação e gerenciamento da rede. O **End Device** será a sonda. O **Gateway** recebe rádio LoRa e encaminha pacotes pela Internet. O **Network Server** processa a rede LoRaWAN. O **Application Server** disponibiliza o payload da aplicação. **MQTT** entrega o uplink à nossa aplicação. **InfluxDB** armazena a série temporal.

## Checklist para hardware real

- [ ] dispositivo LoRaWAN compatível com a frequência/região correta
- [ ] gateway LoRaWAN
- [ ] acesso à Internet no gateway
- [ ] Network Server
- [ ] credenciais do dispositivo
- [ ] DevEUI
- [ ] JoinEUI/AppEUI quando aplicável
- [ ] AppKey quando OTAA
- [ ] configuração regional
- [ ] integração MQTT
- [ ] payload decoder
- [ ] tópico MQTT
- [ ] segurança das credenciais
- [ ] relógio/timestamp definido
- [ ] estratégia de retransmissão
- [ ] intervalo entre uplinks
- [ ] controle de consumo energético

Frequência, potência, duty cycle e demais parâmetros devem seguir a região e regulamentação aplicáveis ao local do projeto. Esta documentação não inventa uma configuração regional.

Quando o hardware chegar, o Network Server publicará no mesmo MQTT. Ajusta-se o parser para o envelope real, marca-se `source=lorawan-real` e mantém-se validação, fila e writer.

