param (
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$ChannelUrl,

    [Parameter(Position = 1)]
    [int]$Limit = 5,

    [Parameter(Position = 2)]
    [int]$MaxDuration = 900,

    [string]$WhisperModel = "small",
    [string]$GeminiModel = "gemini-3.5-flash-lite"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

# Add WinGet FFmpeg to PATH if not already in PATH
$ffmpegPath = Get-ChildItem -Path "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty DirectoryName
if ($ffmpegPath -and ($env:Path -notlike "*$ffmpegPath*")) {
    $env:Path = "$ffmpegPath;$env:Path"
}

Write-Host "`n>>> Chạy Tool Tự Động Hóa Video YouTube -> JSON ChongZi <<<" -ForegroundColor Cyan
Write-Host "Kênh/Video:    $ChannelUrl" -ForegroundColor Yellow
Write-Host "Giới hạn:      $Limit video" -ForegroundColor Yellow
Write-Host "Thời lượng max:$MaxDuration giây" -ForegroundColor Yellow
Write-Host "AI Dịch thuật: Google Gemini ($GeminiModel)" -ForegroundColor Yellow
Write-Host "Whisper Model: $WhisperModel`n" -ForegroundColor Yellow

python "$scriptDir\batch_channel_to_json.py" `
    --channel $ChannelUrl `
    --limit $Limit `
    --max-duration $MaxDuration `
    --whisper-model $WhisperModel `
    --gemini-model $GeminiModel

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[HOÀN TẤT] Dữ liệu JSON đã sẵn sàng trong thư mục video-lessons của ChongZi App!" -ForegroundColor Green
} else {
    Write-Host "`n[CẢNH BÁO] Quá trình chạy có thông báo lỗi. Vui lòng kiểm tra lại log." -ForegroundColor Red
}
