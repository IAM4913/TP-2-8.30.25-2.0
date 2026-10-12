# One-click local start: sets up and launches backend + frontend, then opens the app.
# Usage (from the project folder):  powershell -ExecutionPolicy Bypass -File .\start_local.ps1

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$venvPy = Join-Path $backend '.venv\Scripts\python.exe'

# Backend venv: the pinned numpy/pandas need Python 3.12 or older
if (-not (Test-Path $venvPy)) {
    $created = $false
    foreach ($v in '3.12', '3.11') {
        try {
            & py "-$v" -m venv (Join-Path $backend '.venv') 2>$null
            if (Test-Path $venvPy) { $created = $true; break }
        } catch {}
    }
    if (-not $created) {
        Write-Host "Python 3.12 is required. Install it from https://www.python.org/downloads/release/python-3120/ and re-run." -ForegroundColor Red
        exit 1
    }
}
Write-Host "Installing backend dependencies..." -ForegroundColor Green
& $venvPy -m pip install -q -r (Join-Path $backend 'requirements.txt')

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js is required. Install the LTS version from https://nodejs.org and re-run." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Green
    Push-Location $frontend; npm install; Pop-Location
}

# Start each server in its own window so their logs stay visible
$backendCmd = "cd '$($root.Replace("'", "''"))'; `$env:PYTHONPATH='$($root.Replace("'", "''"))'; & '$($venvPy.Replace("'", "''"))' -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010"
Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $backendCmd | Out-Null
$frontendCmd = "cd '$($frontend.Replace("'", "''"))'; npm run dev"
Start-Process powershell -ArgumentList '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCmd | Out-Null

Write-Host "Waiting for the app to start..." -ForegroundColor Green
for ($i = 0; $i -lt 60; $i++) {
    try {
        Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8010/health -TimeoutSec 2 | Out-Null
        Invoke-WebRequest -UseBasicParsing http://localhost:3001 -TimeoutSec 2 | Out-Null
        Start-Process 'http://localhost:3001'
        Write-Host "Truck Planner is running at http://localhost:3001" -ForegroundColor Green
        exit 0
    } catch { Start-Sleep -Seconds 2 }
}
Write-Host "App didn't come up within 2 minutes - check the two server windows for errors." -ForegroundColor Red
exit 1
