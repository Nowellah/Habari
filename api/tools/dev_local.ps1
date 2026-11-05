#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Django + ngrok for local Africa's Talking testing.

.DESCRIPTION
    1. Reads NGROK_AUTHTOKEN from .env and configures ngrok (idempotent).
    2. Starts Django on port 8000 in the background.
    3. Opens an ngrok HTTPS tunnel on port 8000.
    4. Reads the public URL from the ngrok local API and prints the two
       callback URLs to paste into the Africa's Talking dashboard.

.NOTES
    Requires:
      - ngrok installed (winget install ngrok.ngrok)
      - NGROK_AUTHTOKEN set in .env
      - Python / Django deps installed (pip install -r requirements.txt)
#>

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

# ── Resolve project root (one level up from tools/) ──────────────────────────
$root = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $root ".env"

# ── Load .env into a hashtable ────────────────────────────────────────────────
$envVars = @{}
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and $line -notmatch "^\s*#" -and $line -match "^([^=]+)=(.*)$") {
            $envVars[$Matches[1].Trim()] = $Matches[2].Trim()
        }
    }
} else {
    Write-Error ".env not found at $envFile"
    exit 1
}

# ── 0. Authenticate ngrok from .env ──────────────────────────────────────────
$authToken = $envVars["NGROK_AUTHTOKEN"]
if (-not $authToken) {
    Write-Error "NGROK_AUTHTOKEN is not set in .env"
    exit 1
}
Write-Host "`n[0/3] Configuring ngrok authtoken ..." -ForegroundColor Cyan
ngrok config add-authtoken $authToken | Out-Null
Write-Host "      Done."

# ── 1. Start Django dev server ────────────────────────────────────────────────
Write-Host "[1/4] Starting Django on http://127.0.0.1:$Port ..." -ForegroundColor Cyan
$django = Start-Process -FilePath "python" `
    -ArgumentList "manage.py", "runserver", "127.0.0.1:$Port" `
    -WorkingDirectory $root `
    -PassThru -NoNewWindow
Write-Host "      Django PID: $($django.Id)"

Start-Sleep -Seconds 2

# ── 2. Start AI service ────────────────────────────────────────────────────────
Write-Host "[2/4] Starting AI service on http://127.0.0.1:8001 ..." -ForegroundColor Cyan
$ai = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "ai_service.app:app", "--port", "8001", "--log-level", "warning" `
    -WorkingDirectory $root `
    -PassThru -NoNewWindow
Write-Host "      AI PID:     $($ai.Id)"

Start-Sleep -Seconds 2

# ── 3. Start ngrok tunnel ─────────────────────────────────────────────────────
Write-Host "[3/4] Opening ngrok tunnel on port $Port ..." -ForegroundColor Cyan
$ngrok = Start-Process -FilePath "ngrok" `
    -ArgumentList "http", $Port `
    -PassThru -NoNewWindow
Write-Host "      ngrok  PID: $($ngrok.Id)"

# Wait for ngrok to establish the tunnel
Start-Sleep -Seconds 4

# ── 4. Read public URL from ngrok local API ───────────────────────────────────
Write-Host "[4/4] Reading tunnel URL ..." -ForegroundColor Cyan

$public = $null
$attempts = 0
while (-not $public -and $attempts -lt 6) {
    $attempts++
    try {
        $tunnels = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -ErrorAction Stop
        $public  = ($tunnels.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1).public_url
        if (-not $public) {
            $public = ($tunnels.tunnels | Select-Object -First 1).public_url
        }
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $public) {
    Write-Warning "Could not read tunnel URL from ngrok API. Check http://127.0.0.1:4040 manually."
    $public = "<ngrok-url>"
}

# ── Print callback URLs ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  Africa's Talking callback URLs" -ForegroundColor Green
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host "  SMS  ->  Inbox -> Callback URL:" -ForegroundColor Yellow
Write-Host "    $public/at/sms/" -ForegroundColor White
Write-Host ""
Write-Host "  USSD ->  Service -> Callback URL:" -ForegroundColor Yellow
Write-Host "    $public/at/ussd/" -ForegroundColor White
Write-Host "══════════════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  AI service        : http://127.0.0.1:8001/health" -ForegroundColor DarkGray
Write-Host "  ngrok inspect UI  : http://127.0.0.1:4040" -ForegroundColor DarkGray
Write-Host "  Django            : http://127.0.0.1:$Port" -ForegroundColor DarkGray
Write-Host "  Child chat        : http://127.0.0.1:$Port/chat" -ForegroundColor DarkGray
Write-Host "  USSD simulator    : http://127.0.0.1:$Port/sim/ussd" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press Ctrl+C to stop everything." -ForegroundColor DarkGray
Write-Host ""

# ── Wait; clean up on Ctrl+C ──────────────────────────────────────────────────
try {
    Wait-Process -Id $django.Id
} finally {
    Write-Host "`nStopping processes..." -ForegroundColor Red
    Stop-Process -Id $django.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ai.Id    -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $ngrok.Id  -Force -ErrorAction SilentlyContinue
    Write-Host "Done."
}
