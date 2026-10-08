# Portos Conectados — bancada de dados e comunicação

Esta prova de conceito funciona inteiramente no terminal. O simulador publica mensagens em um broker Eclipse Mosquitto real; o consumer recebe, valida e grava em um InfluxDB real; os testes consultam o banco e comparam os valores. Uma chamada aceita pela API de escrita, sozinha, não é considerada prova.

## O que esta POC comprova

```text
SIMULATED DEVICE
       |
       v
REAL MQTT (TCP/IP)
       |
       v
PYTHON CONSUMER
       |
       v
REAL INFLUXDB
       |
       v
QUERY + VALUE COMPARISON
```

RSSI, SNR, distância e perda configurados no simulador são metadados sintéticos usados para testar software. Eles não comprovam alcance de rádio. O terminal sempre identifica:

```text
RADIO MODE: SIMULATED
PHYSICAL RANGE VALIDATION: NOT PERFORMED
```

## Pré-requisitos

- Windows com Python 3.11 ou mais recente;
- Eclipse Mosquitto instalado diretamente e ouvindo em uma porta TCP;
- InfluxDB 2.x instalado diretamente, com organização, bucket e token;
- nenhum Docker, servidor HTTP ou navegador é usado.

A implementação detecta a versão em `/health`. O adaptador incluído usa a API do InfluxDB 2.x. Se detectar 1.x ou 3.x, mostra a incompatibilidade em vez de assumir que os protocolos são iguais.

## Instalação

No PowerShell, dentro desta pasta:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No Windows 64-bit, baixe o instalador atual na [página oficial do Eclipse Mosquitto](https://mosquitto.org/download/), execute-o e abra um novo terminal. Para um teste local controlado, inicie:

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -v
```

Para o InfluxDB, siga a seção Windows da [instalação oficial do InfluxDB OSS 2.x](https://docs.influxdata.com/influxdb/v2/install/). Ela fornece um arquivo ZIP; expanda em `C:\Program Files\InfluxData\influxdb` e inicie em um terminal:

```powershell
cd 'C:\Program Files\InfluxData\influxdb'
.\influxd.exe
```

O servidor e a CLI `influx` são pacotes separados. Instale também a CLI 2.x e execute `influx setup` em outro terminal. Informe a URL `http://localhost:8086`, uma organização, o bucket `water-quality`, usuário e senha. Guarde o token exibido. Não coloque o token no código nem envie o arquivo `.env` ao controle de versão.

Confirme sem usar navegador:

```powershell
Invoke-RestMethod http://localhost:8086/health
Test-NetConnection localhost -Port 1883
```

## Configuração

Edite `.env`:

```dotenv
MQTT_HOST=192.168.0.20
MQTT_PORT=1883
MQTT_TOPIC=portos/lorawan/uplink
MQTT_QOS=1

INFLUX_URL=http://192.168.0.30:8086
INFLUX_TOKEN=seu-token
INFLUX_ORG=portos-conectados
INFLUX_BUCKET=water-quality
```

`localhost` é apenas o padrão. IPs e nomes DNS permitem distribuir simulador, broker, consumer e banco em máquinas diferentes.

## Primeira execução

```powershell
scripts\check_environment.bat
scripts\start_influxdb.bat
scripts\test_mqtt.bat
scripts\test_influx.bat
scripts\test_end_to_end.bat
scripts\demo.bat
```

Nesta máquina, o InfluxDB 2.9.1 foi instalado em `%LOCALAPPDATA%\PortosConectados\InfluxDB`. O `demo.bat` inicia esse processo automaticamente se a porta 8086 estiver parada.

Para uso contínuo, abra dois terminais:

```powershell
scripts\start_consumer.bat
scripts\start_simulator.bat --devices 10 --messages 100 --profile stress
```

O perfil `realistic` usa intervalo de 30 segundos quando `--interval` não é informado. O perfil `stress` não representa capacidade da interface aérea LoRaWAN.

## Testes

Testes unitários não precisam de serviços:

```powershell
python -m pytest tests\unit tests\hardware
```

Integrações reais são habilitadas explicitamente:

```powershell
$env:RUN_INTEGRATION="1"
python -m pytest tests\integration
```

Execuções isoladas:

```powershell
python -m tests.integration.test_mqtt
python -m tests.integration.test_influx
python -m tests.integration.test_end_to_end
python -m tests.load.load_test --devices 100 --messages 10000
python -m tests.load.load_test --scale --messages-per-device 10
python -m tests.load.test_batch --total 1000
```

`PASS` significa que todas as condições foram verificadas. `FAIL` expõe divergência ou perda. `SKIPPED` significa que o requisito externo não estava habilitado. `NOT EXECUTED` significa que a operação não ocorreu, normalmente por configuração ou serviço ausente.

## Arquivos produzidos

- `evidence/*.json`: esperado, observado, horários e resultado de cada prova;
- `reports/*.json`: dados estruturados para análise;
- `reports/*.txt`: resumo legível;
- `reports/*_scale.csv`: comparação progressiva;
- `pending_queue.db`: mensagens aguardando InfluxDB;
- `system_state.db`: contadores, ordem dos frames e rastreamento local.

## Rede entre computadores

Na máquina A, configure `MQTT_HOST` com o IP da máquina B e execute o simulador. Na máquina B, permita a porta do Mosquitto no firewall e configure autenticação. Na máquina C, use o mesmo MQTT e configure `INFLUX_URL` com a máquina que hospeda o banco. Isso é um **NETWORK DATA PIPELINE TEST**: comprova TCP/IP real, não LoRaWAN.

Veja [docs/arquitetura.md](docs/arquitetura.md), [docs/testes.md](docs/testes.md) e [GUIA_APRESENTACAO.md](GUIA_APRESENTACAO.md).

## Relatório acadêmico

O texto-fonte está em [docs/portos_conectados_poc.tex](docs/portos_conectados_poc.tex) e o PDF compilado em [output/pdf/portos_conectados_poc.pdf](output/pdf/portos_conectados_poc.pdf). O documento descreve método, arquitetura, contrato de dados, reprodução, resultados, gráficos, limitações e trabalho futuro.

Para recompilar com MiKTeX ou TeX Live:

```powershell
New-Item -ItemType Directory -Force output\pdf | Out-Null
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=output\pdf docs\portos_conectados_poc.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=output\pdf docs\portos_conectados_poc.tex
```

Os dados consolidados usados nos gráficos estão em `results/`. Eles são resultados desta máquina e não substituem uma nova execução no ambiente de quem reproduzir a POC.
