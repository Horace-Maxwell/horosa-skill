$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $Root "..\\runtime\\windows"
$PythonBin = Join-Path $RuntimeRoot "python\\python.exe"
$JavaBin = Join-Path $RuntimeRoot "java\\bin\\java.exe"
$JarPath = Join-Path $RuntimeRoot "bundle\\astrostudyboot.jar"
$ChartPort = if ($env:HOROSA_CHART_PORT) { $env:HOROSA_CHART_PORT } else { "8899" }
$BackendPort = if ($env:HOROSA_SERVER_PORT) { $env:HOROSA_SERVER_PORT } else { "9999" }
$LogRoot = if ($env:HOROSA_LOG_ROOT) { $env:HOROSA_LOG_ROOT } else { Join-Path $Root ".horosa-local-logs" }
$RunTag = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $LogRoot $RunTag
$PyOutLog = Join-Path $LogDir "astropy.stdout.log"
$PyErrLog = Join-Path $LogDir "astropy.stderr.log"
$JavaOutLog = Join-Path $LogDir "astrostudyboot.stdout.log"
$JavaErrLog = Join-Path $LogDir "astrostudyboot.stderr.log"
$PyPidPath = Join-Path $Root ".horosa_py.pid"
$JavaPidPath = Join-Path $Root ".horosa_java.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $PythonBin)) { throw "python runtime not found: $PythonBin" }
if (-not (Test-Path $JavaBin)) { throw "java runtime not found: $JavaBin" }
if (-not (Test-Path $JarPath)) { throw "astrostudyboot.jar not found: $JarPath" }

$AstropyRoot = Join-Path $Root "astropy"
$FlatlibRoot = Join-Path $Root "flatlib-ctrad2"
$ChartEntry = Join-Path $AstropyRoot "websrv\\webchartsrv.py"

if (-not $env:HOME) {
  if ($env:USERPROFILE) {
    $env:HOME = $env:USERPROFILE
  } else {
    $env:HOME = [Environment]::GetFolderPath("UserProfile")
  }
}
if (-not $env:USERPROFILE) {
  $env:USERPROFILE = $env:HOME
}
if (-not $env:HOMEDRIVE) {
  $Drive = [System.IO.Path]::GetPathRoot($env:USERPROFILE)
  if ($Drive) {
    $env:HOMEDRIVE = $Drive.TrimEnd('\')
  }
}
if (-not $env:HOMEPATH -and $env:HOMEDRIVE) {
  $env:HOMEPATH = $env:USERPROFILE.Substring($env:HOMEDRIVE.Length)
}

$env:HOROSA_CHART_PORT = $ChartPort
$env:PYTHONPATH = "{0};{1}" -f $AstropyRoot, $FlatlibRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$PyBootCode = @"
import runpy
import sys

for path in [r"$FlatlibRoot", r"$AstropyRoot"]:
    if path not in sys.path:
        sys.path.insert(0, path)

runpy.run_path(r"$ChartEntry", run_name="__main__")
"@

$PyProc = Start-Process -FilePath $PythonBin -ArgumentList "-c", $PyBootCode -WorkingDirectory $Root -RedirectStandardOutput $PyOutLog -RedirectStandardError $PyErrLog -PassThru -WindowStyle Hidden
$JavaProc = Start-Process -FilePath $JavaBin -ArgumentList "-jar", $JarPath, "--server.port=$BackendPort", "--astrosrv=http://127.0.0.1:$ChartPort", "--mongodb.ip=127.0.0.1", "--redis.ip=127.0.0.1" -WorkingDirectory $Root -RedirectStandardOutput $JavaOutLog -RedirectStandardError $JavaErrLog -PassThru -WindowStyle Hidden

$PyProc.Id | Set-Content -Encoding utf8 $PyPidPath
$JavaProc.Id | Set-Content -Encoding utf8 $JavaPidPath

$Deadline = (Get-Date).AddSeconds(180)
while ((Get-Date) -lt $Deadline) {
  $ChartReady = $false
  $BackendReady = $false
  try {
    $chartRsp = Invoke-WebRequest -Uri "http://127.0.0.1:$ChartPort/" -UseBasicParsing -TimeoutSec 2
    $ChartReady = $chartRsp.StatusCode -lt 500
  } catch {}
  try {
    $backendRsp = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/common/time" -UseBasicParsing -TimeoutSec 2
    $BackendReady = $backendRsp.StatusCode -lt 500
  } catch {}
  if ($ChartReady -and $BackendReady) {
    Write-Host "services are ready."
    Write-Host "backend:  http://127.0.0.1:$BackendPort"
    Write-Host "chartpy:  http://127.0.0.1:$ChartPort"
    exit 0
  }
  Start-Sleep -Seconds 1
}

throw "Windows Horosa runtime did not become ready in time."
