$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyPidPath = Join-Path $Root ".horosa_py.pid"
$JavaPidPath = Join-Path $Root ".horosa_java.pid"

foreach ($pidPath in @($PyPidPath, $JavaPidPath)) {
  if (Test-Path $pidPath) {
    $pidText = (Get-Content $pidPath -Raw).Trim()
    if ($pidText) {
      Stop-Process -Id ([int]$pidText) -Force
    }
    Remove-Item $pidPath -Force
  }
}

Write-Host "stop requested"
