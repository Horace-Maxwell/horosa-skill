$ErrorActionPreference = "Stop"

param(
  [Parameter(Mandatory = $true)]
  [string]$PayloadRoot,

  [string]$OutputDir = ""
)

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path (Split-Path -Parent $PSScriptRoot) "dist/runtime"
}

$ResolvedPayloadRoot = (Resolve-Path $PayloadRoot).Path
$ManifestPath = Join-Path $ResolvedPayloadRoot "runtime-manifest.json"
if (-not (Test-Path $ManifestPath)) {
  throw "runtime-manifest.json not found under $ResolvedPayloadRoot"
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$Version = $Manifest.version
$Platform = $Manifest.platform

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$ZipPath = Join-Path $OutputDir ("horosa-runtime-{0}-{1}.zip" -f $Version, $Platform)
if (Test-Path $ZipPath) {
  Remove-Item $ZipPath -Force
}

Compress-Archive -Path (Join-Path $ResolvedPayloadRoot "*") -DestinationPath $ZipPath
Write-Host "Created Windows runtime archive: $ZipPath"
