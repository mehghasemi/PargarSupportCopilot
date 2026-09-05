param(
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python پیدا نشد. Python 3.11 یا جدیدتر نصب کنید و دوباره اجرا کنید." -ForegroundColor Red
    exit 1
}

Write-Host "بررسی و نصب وابستگی‌ها..." -ForegroundColor Cyan
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "خواندن Snapshot واقعی از CRM با دسترسی فقط‌خواندنی..." -ForegroundColor Yellow
python scripts\sync_crm_to_local.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "همگام‌سازی CRM انجام نشد؛ برنامه با داده قبلی یا فرضی ادامه نمی‌دهد." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "اجرای Prototype روی http://127.0.0.1:$Port/" -ForegroundColor Green
if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:$Port/portal.html"
}
python scripts\local_app.py --port $Port
