$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
  python "$projectRoot\scripts\download-tiktok.py" $args
  if ($LASTEXITCODE -ne 0) {
    throw "TikTok download failed."
  }
} finally {
  Pop-Location
}
