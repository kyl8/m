@echo off
setlocal
set "INFLUX_EXE=%LOCALAPPDATA%\PortosConectados\InfluxDB\2.9.1\influxd.exe"
set "INFLUX_DATA=%LOCALAPPDATA%\PortosConectados\InfluxDB\data"
set "INFLUX_LOGS=%LOCALAPPDATA%\PortosConectados\InfluxDB\logs"

if not exist "%INFLUX_EXE%" (
    echo [FAIL] InfluxDB nao encontrado em %INFLUX_EXE%
    exit /b 1
)

powershell -NoProfile -Command "$c=[Net.Sockets.TcpClient]::new(); try{$ok=$c.ConnectAsync('127.0.0.1',8086).Wait(500)-and$c.Connected}catch{$ok=$false};$c.Dispose();if($ok){exit 0}else{exit 1}"
if %errorlevel% equ 0 exit /b 0

if not exist "%INFLUX_DATA%\engine" mkdir "%INFLUX_DATA%\engine"
if not exist "%INFLUX_LOGS%" mkdir "%INFLUX_LOGS%"

powershell -NoProfile -Command "Start-Process -FilePath '%INFLUX_EXE%' -ArgumentList @('--bolt-path','%INFLUX_DATA%\influxd.bolt','--engine-path','%INFLUX_DATA%\engine','--http-bind-address','127.0.0.1:8086','--reporting-disabled=true') -WindowStyle Hidden -RedirectStandardOutput '%INFLUX_LOGS%\influxd.stdout.log' -RedirectStandardError '%INFLUX_LOGS%\influxd.stderr.log'"
echo [INFO] InfluxDB iniciado em 127.0.0.1:8086
endlocal
