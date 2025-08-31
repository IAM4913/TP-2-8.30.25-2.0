param(
    [switch]$ReuseEnv
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

    & $venvPy -m pip install -r requirements.txt

    $projectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
    $env:PYTHONPATH = $projectRoot.Path
    & $venvPy -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8010
}
finally {
    Pop-Location
}


