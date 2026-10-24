$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path $PSScriptRoot -Parent)
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
$env:PYTHONPATH = (Get-Location).Path
foreach ($test in @('test-transmission.py', 'test-text-pages.py', 'test-debug-controller.py', 'test-app-ui.py', 'test-device-picker.py', 'test-ui-language.py')) {
    & $python $test
    if ($LASTEXITCODE -ne 0) { throw "Failed: $test" }
}
