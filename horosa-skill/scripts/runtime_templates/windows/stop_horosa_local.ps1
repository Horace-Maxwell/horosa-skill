$ErrorActionPreference = "SilentlyContinue"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $Root "..\\runtime\\windows"
# Normalize (resolve `..` + collapse separators) so these match the OS-canonical Get-Process .Path in the
# ownership check below — an unnormalized path with `..` never -ieq's the running image and the kill is skipped.
$PythonBin = [System.IO.Path]::GetFullPath((Join-Path $RuntimeRoot "python\\python.exe"))
$JavaBin = [System.IO.Path]::GetFullPath((Join-Path $RuntimeRoot "java\\bin\\java.exe"))
$PyPidPath = Join-Path $Root ".horosa_py.pid"
$JavaPidPath = Join-Path $Root ".horosa_java.pid"

$survivors = @()
foreach ($pair in @(@{ Pid = $PyPidPath; Exe = $PythonBin }, @{ Pid = $JavaPidPath; Exe = $JavaBin })) {
  $pidPath = $pair.Pid
  $expectedExe = $pair.Exe
  if (-not (Test-Path $pidPath)) { continue }
  $pidText = (Get-Content $pidPath -Raw).Trim()
  $pidInt = 0
  if ($pidText -and [int]::TryParse($pidText, [ref]$pidInt)) {
    $proc = Get-Process -Id $pidInt -ErrorAction SilentlyContinue
    # Only force-kill if the PID still maps to OUR runtime image. Windows recycles PIDs, so a stale
    # PID could now belong to an unrelated process (e.g. the user's editor) — never kill that.
    if ($proc -and $proc.Path -and ($proc.Path -ieq $expectedExe)) {
      Stop-Process -Id $pidInt -Force
      # Confirm it actually exited before removing the pid file, so a hung process is not silently
      # orphaned (and unreachable on the next stop because the pid file is gone).
      $gone = $false
      for ($i = 0; $i -lt 10; $i++) {
        Start-Sleep -Milliseconds 300
        if (-not (Get-Process -Id $pidInt -ErrorAction SilentlyContinue)) { $gone = $true; break }
      }
      if ($gone) { Remove-Item $pidPath -Force } else { $survivors += $pidInt }
    } else {
      # PID is dead or reassigned to a foreign process: drop the stale pid file, do not kill anything.
      Remove-Item $pidPath -Force
    }
  } else {
    Remove-Item $pidPath -Force
  }
}

if ($survivors.Count -gt 0) {
  Write-Error ("stop incomplete: runtime PID(s) still alive after kill: {0}" -f ($survivors -join ", "))
  exit 1
}

Write-Host "stop requested"
exit 0
