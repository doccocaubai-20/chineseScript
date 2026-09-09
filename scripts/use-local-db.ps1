$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
$prismaEnvPath = Join-Path $projectRoot "apps\api\.env"

if (-not (Test-Path $envPath)) {
  Copy-Item (Join-Path $projectRoot ".env.example") $envPath
}

$lines = Get-Content $envPath
$databaseLine = "DATABASE_URL=postgresql://app:app@localhost:55432/chinese_video"
$updated = $false
$result = foreach ($line in $lines) {
  if ($line -match "^DATABASE_URL=") {
    $updated = $true
    $databaseLine
  } else {
    $line
  }
}

if (-not $updated) {
  $result += $databaseLine
}

Set-Content -Path $envPath -Value $result -Encoding utf8
Set-Content -Path $prismaEnvPath -Value $databaseLine -Encoding utf8
Write-Host "Configured .env to use local PostgreSQL at localhost:55432."
