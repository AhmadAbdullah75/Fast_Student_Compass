param([switch]$SkipBuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath "$PSScriptRoot/.venv/Scripts/python.exe")) {
    throw 'Create .venv and install requirements-lock.txt first. See README.md.'
}
if (-not $SkipBuild) {
    Push-Location -LiteralPath "$PSScriptRoot/frontend"
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            & npm.cmd ci
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'React build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Open http://localhost:8501 - press Ctrl+C here to stop.'
& "$PSScriptRoot/.venv/Scripts/python.exe" -m uvicorn compass.web:app --host 127.0.0.1 --port 8501
