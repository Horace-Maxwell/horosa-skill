$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $Root "..\\runtime\\windows"
# Normalize (resolve the `..` + collapse separators) so these match the OS-canonical Get-Process .Path
# in the PID-ownership checks below — an unnormalized path with `..` never -ieq's the running image path.
$PythonBin = [System.IO.Path]::GetFullPath((Join-Path $RuntimeRoot "python\\python.exe"))
$JavaBin = [System.IO.Path]::GetFullPath((Join-Path $RuntimeRoot "java\\bin\\java.exe"))
$JarPath = [System.IO.Path]::GetFullPath((Join-Path $RuntimeRoot "bundle\\astrostudyboot.jar"))
$ChartPort = if ($env:HOROSA_CHART_PORT) { $env:HOROSA_CHART_PORT } else { "8899" }
$BackendPort = if ($env:HOROSA_SERVER_PORT) { $env:HOROSA_SERVER_PORT } else { "9999" }
$LogRoot = if ($env:HOROSA_LOG_ROOT) { $env:HOROSA_LOG_ROOT } else { Join-Path $Root ".horosa-local-logs" }
$RunTag = Get-Date -Format "yyyyMMdd_HHmmss"
$LogDir = Join-Path $LogRoot $RunTag
$PyOutLog = Join-Path $LogDir "astropy.stdout.log"
$PyErrLog = Join-Path $LogDir "astropy.stderr.log"
$JavaOutLog = Join-Path $LogDir "astrostudyboot.stdout.log"
$JavaErrLog = Join-Path $LogDir "astrostudyboot.stderr.log"
$PyBootstrapPath = Join-Path $LogDir "astropy_bootstrap.py"
$PyPidPath = Join-Path $Root ".horosa_py.pid"
$JavaPidPath = Join-Path $Root ".horosa_java.pid"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $PythonBin)) { throw "python runtime not found: $PythonBin" }
if (-not (Test-Path $JavaBin)) { throw "java runtime not found: $JavaBin" }
if (-not (Test-Path $JarPath)) { throw "astrostudyboot.jar not found: $JarPath" }

# Return the live process for a recorded PID ONLY if it still maps to our own runtime image.
# Windows recycles PIDs aggressively, so a bare Stop-Process on a stale PID could hit an unrelated
# process; matching on the expected exe path makes start/stop safe against PID reuse.
function Get-OwnedProcess([string]$pidPath, [string]$expectedExe) {
  if (-not (Test-Path $pidPath)) { return $null }
  $pidText = (Get-Content $pidPath -Raw).Trim()
  if (-not $pidText) { return $null }
  $pidInt = 0
  if (-not [int]::TryParse($pidText, [ref]$pidInt)) { return $null }
  $proc = Get-Process -Id $pidInt -ErrorAction SilentlyContinue
  if ($proc -and $proc.Path -and ($proc.Path -ieq $expectedExe)) { return $proc }
  return $null
}

# Stale / already-running guard: if a PRIOR run's own processes are still alive (e.g. after a slow
# start where the caller gave up but the children kept coming up), stop them first so we never
# orphan them by clobbering their pid files below. Emit the marker string the runtime manager keys on.
$priorPy = Get-OwnedProcess $PyPidPath $PythonBin
$priorJava = Get-OwnedProcess $JavaPidPath $JavaBin
if ($priorPy -or $priorJava) {
  Write-Host "pid files already exist; stopping prior runtime before relaunch"
  foreach ($p in @($priorPy, $priorJava)) { if ($p) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
  Start-Sleep -Seconds 2
}
# Drop any pid files now (stale, or just-stopped) so a later stop never force-kills a recycled PID.
foreach ($pidPath in @($PyPidPath, $JavaPidPath)) {
  if (Test-Path $pidPath) { Remove-Item $pidPath -Force -ErrorAction SilentlyContinue }
}

# Port-collision guard: fail fast with a clear, actionable message instead of waiting out the full
# readiness deadline when something else already holds the chart/backend port.
function Test-PortListening([int]$port) {
  return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}
foreach ($pc in @(@{ Name = "chart"; Port = [int]$ChartPort }, @{ Name = "backend"; Port = [int]$BackendPort })) {
  if (Test-PortListening $pc.Port) {
    $holder = Get-NetTCPConnection -State Listen -LocalPort $pc.Port -ErrorAction SilentlyContinue | Select-Object -First 1
    $holderPid = if ($holder) { $holder.OwningProcess } else { "?" }
    throw ("port {0} ({1} service) already in use by PID {2}; stop that process or set HOROSA_CHART_PORT / HOROSA_SERVER_PORT to free ports before starting" -f $pc.Port, $pc.Name, $holderPid)
  }
}

$AstropyRoot = Join-Path $Root "astropy"
$FlatlibRoot = Join-Path $Root "flatlib-ctrad2"
$VendorRoot = Join-Path $Root "vendor"
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
# vendor/ carries the ken engines (kinqimen/kintaiyi/kinjinkou) the chart service mounts;
# keep it on PYTHONPATH to mirror the macOS launcher's PYTHONPATH_ASTRO.
$env:PYTHONPATH = "{0};{1};{2}" -f $AstropyRoot, $FlatlibRoot, $VendorRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$PyBootCode = @"
import runpy
import sys

for path in [r"$FlatlibRoot", r"$AstropyRoot", r"$VendorRoot"]:
    if path not in sys.path:
        sys.path.insert(0, path)

runpy.run_path(r"$ChartEntry", run_name="__main__")
"@
Set-Content -LiteralPath $PyBootstrapPath -Value $PyBootCode -Encoding utf8

$PyProc = Start-Process -FilePath $PythonBin -ArgumentList @($PyBootstrapPath) -WorkingDirectory $Root -RedirectStandardOutput $PyOutLog -RedirectStandardError $PyErrLog -PassThru -WindowStyle Hidden
# -Dfile.encoding/-Dsun.jnu.encoding=UTF-8: the bundled Temurin 17 is pre-JEP-400 and defaults to the
# OS code page (Cp1252/Cp936 on Windows), which cannot represent CJK; pin UTF-8 so any jar resource the
# backend reads via a charset-defaulting API (star/格局/神煞 tables) is decoded correctly. No-op on a
# healthy run; eliminates the whole JDK-17 codepage class of bug.
$JavaProc = Start-Process -FilePath $JavaBin -ArgumentList "-Dfile.encoding=UTF-8", "-Dsun.jnu.encoding=UTF-8", "-jar", $JarPath, "--server.port=$BackendPort", "--astrosrv=http://127.0.0.1:$ChartPort", "--mongodb.ip=127.0.0.1", "--redis.ip=127.0.0.1" -WorkingDirectory $Root -RedirectStandardOutput $JavaOutLog -RedirectStandardError $JavaErrLog -PassThru -WindowStyle Hidden

$PyProc.Id | Set-Content -Encoding utf8 $PyPidPath
$JavaProc.Id | Set-Content -Encoding utf8 $JavaPidPath

# Readiness: require BOTH the Python chart service (:8899) and the Java backend (:9999) — same contract
# the runtime manager enforces. The Java backend (Spring Boot) retries Mongo/Redis on boot and can be
# slow on a bare box, so the window is 300s (was 180s) to avoid the historical false-failure where the
# script threw while the backend was still a few seconds from ready. (A future option is to gate exit-0
# on the chart service alone — ken/神数 only need :8899 — but that requires a matching change to the
# manager's all-endpoints readiness check, so it is intentionally left as a both-required gate here.)
$Deadline = (Get-Date).AddSeconds(300)
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
