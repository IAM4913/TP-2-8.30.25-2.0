param(
    [switch]$ReuseEnv,
    [switch]$SkipInstall,
    [switch]$Detach
)

$ErrorActionPreference = 'Stop'

Push-Location $PSScriptRoot
try {
    if (-not $ReuseEnv) {
        if (-not (Test-Path .venv)) {
            python -m venv .venv
        }
    }

    $venvActivate = Join-Path .venv 'Scripts\Activate.ps1'
    if (Test-Path $venvActivate) { . $venvActivate }

    # Prefer venv python; fall back to system python
    $venvPy = Join-Path .venv 'Scripts\python.exe'
    if (-not (Test-Path $venvPy)) { $venvPy = 'python' }

    # Install dependencies only if requested or when requirements changed
    if (-not $SkipInstall) {
        $hashFile = Join-Path .venv '.requirements.hash'
        $currentHash = (Get-FileHash -Algorithm SHA256 requirements.txt).Hash
        $previousHash = if (Test-Path $hashFile) { Get-Content $hashFile -ErrorAction SilentlyContinue } else { '' }
        if ($currentHash -ne $previousHash) {
            & $venvPy -m pip install -r requirements.txt
            $currentHash | Set-Content -Path $hashFile -Encoding ASCII
        }
    }

    $projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
    $env:PYTHONPATH = $projectRoot.Path
    $reloadDir = Join-Path $PSScriptRoot 'app'

    if ($Detach) {
        # Launch a new PowerShell window that sets PYTHONPATH then starts Uvicorn
        $escapedRoot = $PSScriptRoot.Replace("'", "''")
        $escapedProj = $projectRoot.Path.Replace("'", "''")
        $py = if (Test-Path $venvPy) { (Resolve-Path $venvPy).Path } else { 'python' }
        $cmd = "cd '$escapedRoot'; $env:PYTHONPATH='$escapedProj'; & '$py' -m uvicorn backend.app.main:app --reload --reload-dir '$reloadDir' --host 127.0.0.1 --port 8010"
        Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-Command', $cmd | Out-Null
        Write-Host "Started backend in a new PowerShell window on http://127.0.0.1:8010"
    }
    else {
        & $venvPy -m uvicorn backend.app.main:app --reload --reload-dir "$reloadDir" --host 127.0.0.1 --port 8010
    }
}
finally {
    Pop-Location
}


