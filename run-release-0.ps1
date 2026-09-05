param(
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found. Install Python 3.11 or newer." -ForegroundColor Red
    exit 1
}

Write-Host "Checking and installing dependencies..." -ForegroundColor Cyan
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Reading the real CRM snapshot in read-only mode..." -ForegroundColor Yellow
python scripts\sync_crm_to_local.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "CRM synchronization failed. The application will not use fallback data." -ForegroundColor Red
    exit $LASTEXITCODE
}

$url = "http://127.0.0.1:$Port/"
$serverReady = $false
try {
    $probe = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
    $serverReady = $probe.StatusCode -eq 200
} catch {
    $serverReady = $false
}

if (-not $serverReady) {
    Write-Host "Starting local application server..." -ForegroundColor Cyan
    Start-Process python -ArgumentList "scripts\local_app.py --port $Port" -WorkingDirectory $projectRoot -WindowStyle Hidden
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $probe = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($probe.StatusCode -eq 200) {
                $serverReady = $true
                break
            }
        } catch {
            # Server is still starting.
        }
    }
}

if (-not $serverReady) {
    Write-Host "The local application server did not become ready: $url" -ForegroundColor Red
    exit 1
}

Write-Host "Application is ready: $url" -ForegroundColor Green
if (-not $NoBrowser) {
    Start-Process $url
}
