param(
    [switch]$Install
)

$ErrorActionPreference = 'Stop'

Push-Location $PSScriptRoot
try {
    if ($Install) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Green
        npm install
    }
    
    Write-Host "Starting frontend development server..." -ForegroundColor Green
    npm run dev
}
finally {
    Pop-Location
}
