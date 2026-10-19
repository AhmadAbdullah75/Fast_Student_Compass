param([string]$RunName = ("publication-" + [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")))
$ErrorActionPreference = "Stop"
if ($RunName -notmatch '^[a-zA-Z0-9-]+$') { throw "Use letters, digits and hyphens for the run name." }
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
Push-Location $projectRoot
try {
    Write-Host "Running local regressions, then real free-tier API evaluation. No publishing or billing changes."
    & $python -m pytest -q --junitxml=reports/publication-python.xml
    if ($LASTEXITCODE -ne 0) { throw "Python regression failure." }
    Push-Location frontend
    try {
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failure." }
        & npx.cmd playwright test
        if ($LASTEXITCODE -ne 0) { throw "Browser regression failure." }
    } finally { Pop-Location }
    & $python tools/publication_system_checks.py
    if ($LASTEXITCODE -ne 0) { throw "Isolated process/configuration checks failed." }
    & $python -m compass.benchmark --run $RunName --suite evaluation/publication/question-bank.json --interval 7
    if ($LASTEXITCODE -ne 0) { throw "Question runner failed; preserve and inspect the checkpoint." }
    & $python tools/publication_report.py --run $RunName
    if ($LASTEXITCODE -ne 0) { throw "Report assembly failed." }
    $report = Get-Content -LiteralPath (Join-Path $projectRoot "reports\benchmark\$RunName.json") -Raw | ConvertFrom-Json
    if ($report.results.Count -ne 187 -or @($report.results | Where-Object { $_.status -ne 'completed' }).Count -gt 0) {
        Write-Warning "The 187-question run is incomplete or contains failed attempts. No release pass is assigned. Inspect its report and quota."
        exit 2
    }
    & $python tools/publication_workflows.py --run $RunName --interval 10
    if ($LASTEXITCODE -ne 0) { throw "Conversation runner failed." }
    $workflow = Get-Content -LiteralPath (Join-Path $projectRoot "reports\publication\$RunName\workflows.json") -Raw | ConvertFrom-Json
    if ($workflow.results.Count -ne 10 -or @($workflow.results | Where-Object { $_.execution_status -ne 'COMPLETED' }).Count -gt 0) {
        Write-Warning "Conversation execution is incomplete. No release pass is assigned."
        exit 2
    }
    & node tools/publication_live_browser.mjs "$RunName-fresh"
    if ($LASTEXITCODE -ne 0) { throw "Fresh browser test failed." }
    $fresh = Get-Content -LiteralPath (Join-Path $projectRoot "reports\publication\$RunName-fresh\results.json") -Raw | ConvertFrom-Json
    if (-not $fresh.full_fresh_live_gate_passed) {
        Write-Warning "Fresh live answering is blocked or failed. No release pass is assigned."
        exit 2
    }
    Write-Host "Execution reports saved. Source-based semantic scoring and the human policy review are still required; this script never declares publication readiness."
} finally { Pop-Location }
