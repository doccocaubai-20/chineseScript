$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
  docker compose up -d postgres
  if ($LASTEXITCODE -ne 0) {
    throw "Could not start the local PostgreSQL container."
  }
  corepack pnpm db:migrate
  if ($LASTEXITCODE -ne 0) {
    throw "Could not apply PostgreSQL migrations."
  }
} finally {
  Pop-Location
}

$ffmpegPath = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty DirectoryName
if ($ffmpegPath) {
  $env:Path = "$ffmpegPath;$env:Path"
}
$workerCommand = "Set-Location '$projectRoot'; python -m uvicorn app.main:app --app-dir services\ai-worker --host 127.0.0.1 --port 8000"
$apiCommand = "Set-Location '$projectRoot'; corepack pnpm --filter api start:dev"
$webCommand = "Set-Location '$projectRoot'; corepack pnpm --filter web dev"

Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $workerCommand
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $apiCommand
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $webCommand

Write-Host "Started local services in separate PowerShell windows."
Write-Host "Worker: http://localhost:8000/health"
Write-Host "API:    http://localhost:3001/health"
Write-Host "Web:    http://localhost:3000"
