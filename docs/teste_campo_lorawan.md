# Teste de campo LoRaWAN futuro

Este ensaio só poderá ser executado com dispositivo, gateway, Network Server e integração reais.

1. Fixar o gateway e registrar posição, altura, antena, firmware e conectividade.
2. Sincronizar relógios e registrar configuração regional permitida.
3. Levar a sonda a pontos progressivos, por exemplo 100 m, 250 m, 500 m, 1 km e 2 km, ajustando os pontos às condições e regras locais.
4. Em cada ponto, enviar uma quantidade definida de mensagens sem mudar outras variáveis.
5. Registrar distância medida, mensagens enviadas, recebidas, PDR, RSSI, SNR, spreading factor, gateway e tempo.
6. Anotar obstáculos, relevo, clima, posição e perda de visada.
7. Consultar no InfluxDB cada UUID recebido e separar perda no rádio de falha posterior.

PDR = mensagens recebidas / mensagens enviadas × 100. Não há valores fictícios neste documento. Resultados de RSSI/SNR simulados não entram na tabela de campo.

