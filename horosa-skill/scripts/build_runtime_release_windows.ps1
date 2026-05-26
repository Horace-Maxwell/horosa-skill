param(
  [Parameter(Mandatory = $true)]
  [string]$PayloadRoot,

  [string]$OutputDir = ""
)

# NOTE: `param(...)` MUST be the first statement in a PowerShell script, so $ErrorActionPreference
# is set *after* it (not before — that is a parse error).
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path (Split-Path -Parent $PSScriptRoot) "dist/runtime"
}

$ResolvedPayloadRoot = (Resolve-Path $PayloadRoot).Path

# The release archive layout (build_runtime_release_windows.py + verify_runtime_release.py) requires
# every entry to be prefixed with `runtime-payload/`. That only holds if we archive a directory that
# is literally named `runtime-payload`, so refuse anything else rather than emit a non-conforming zip.
if ((Split-Path -Leaf $ResolvedPayloadRoot) -ne "runtime-payload") {
  throw "PayloadRoot must point to a directory named 'runtime-payload' (got '$ResolvedPayloadRoot')."
}

$ManifestPath = Join-Path $ResolvedPayloadRoot "runtime-manifest.json"
if (-not (Test-Path $ManifestPath)) {
  throw "runtime-manifest.json not found under $ResolvedPayloadRoot"
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$Version = $Manifest.version
$Platform = $Manifest.platform

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
# Filename convention matches the Python builder: horosa-runtime-<platform>-v<version>.zip
$ZipPath = Join-Path $OutputDir ("horosa-runtime-{0}-v{1}.zip" -f $Platform, $Version)
if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}

# Archive the `runtime-payload` directory itself (NOT its contents via `\*`) so every entry keeps the
# `runtime-payload/` prefix that verify_runtime_release.py asserts.
Compress-Archive -Path $ResolvedPayloadRoot -DestinationPath $ZipPath
Write-Host "Created Windows runtime archive: $ZipPath"
