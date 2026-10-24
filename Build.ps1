param([string]$Python = 'py', [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython)) {
    if ($Python -eq 'py') { & $Python -3.12 -m venv .venv }
    else { & $Python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 x64 with Tcl/Tk support.' }
}
if (-not $SkipInstall) {
    & $venvPython -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $venvPython scripts/check-version.py
if ($LASTEXITCODE -ne 0) { throw 'Version metadata is inconsistent.' }
& $venvPython -m PyInstaller --noconfirm --clean --distpath . --workpath build Divoom.spec
if ($LASTEXITCODE -ne 0) { throw 'Divoom build failed.' }
Write-Host 'Built Divoom.exe'
