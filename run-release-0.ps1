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
$requiredApiVersion = "2026-09-05-view-scope-2"
$serverReady = $false
try {
    $info = Invoke-RestMethod -Uri "$url`api/app-info" -TimeoutSec 2 -ErrorAction Stop
    $serverReady = $info.api_version -eq $requiredApiVersion
} catch {
    $serverReady = $false
}

if (-not $serverReady) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        foreach ($connection in $connections) {
            $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
            if ($process -and $process.Path -like "*python*") {
                Stop-Process -Id $connection.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Host "Could not replace the old local server process automatically." -ForegroundColor Yellow
    }
    Write-Host "Starting local application server..." -ForegroundColor Cyan
    Start-Process python -ArgumentList "scripts\local_app.py --port $Port" -WorkingDirectory $projectRoot -WindowStyle Hidden
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            $probe = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            $info = Invoke-RestMethod -Uri "$url`api/app-info" -TimeoutSec 2 -ErrorAction Stop
            if ($info.api_version -eq $requiredApiVersion) {
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
