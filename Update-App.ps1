param(
    [Parameter(Mandatory=$true)][int]$AppProcessId,
    [Parameter(Mandatory=$true)][string]$Target,
    [Parameter(Mandatory=$true)][string]$Staging,
    [switch]$NoRestart
)
$ErrorActionPreference = 'Stop'
# The previous one-file instance removes its _MEI directory on exit.
# Restart as an independent instance instead of reusing that directory.
$env:PYINSTALLER_RESET_ENVIRONMENT = '1'
$targetPath = [IO.Path]::GetFullPath($Target)
$stagingPath = [IO.Path]::GetFullPath($Staging)
$appFolder = [IO.Path]::GetDirectoryName($targetPath)
if ([IO.Path]::GetFileName($targetPath) -ne 'Divoom.exe' -or
    [IO.Path]::GetDirectoryName($stagingPath) -ne $appFolder -or
    -not [IO.Path]::GetFileName($stagingPath).StartsWith('.divoom-update-')) {
    throw 'Invalid update paths'
}
$replacement = Join-Path $stagingPath 'Divoom.exe'
$backup = Join-Path $appFolder 'Divoom.previous.exe'
$log = Join-Path $appFolder 'update.log'
try {
    Set-Content -LiteralPath (Join-Path $stagingPath 'ready') -Value 'ready'
    Wait-Process -Id $AppProcessId -Timeout 120 -ErrorAction SilentlyContinue
    if (Get-Process -Id $AppProcessId -ErrorAction SilentlyContinue) { throw 'Application is still running' }
    $moved = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            # PyInstaller's parent may briefly hold the EXE after the child exits.
            Move-Item -LiteralPath $targetPath -Destination $backup -Force
            $moved = $true
            break
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $moved) { throw 'Could not back up the running executable' }
    try {
        Move-Item -LiteralPath $replacement -Destination $targetPath
    } catch {
        Move-Item -LiteralPath $backup -Destination $targetPath -Force
        throw
    }
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Update installed; previous EXE: Divoom.previous.exe"
    if (-not $NoRestart) { Start-Process -FilePath $targetPath -WorkingDirectory $appFolder -WindowStyle Normal }
} catch {
    Add-Content -LiteralPath $log -Value "$(Get-Date -Format o) Update failed: $_"
    if (-not $NoRestart -and (Test-Path -LiteralPath $targetPath)) {
        Start-Process -FilePath $targetPath -WorkingDirectory $appFolder -WindowStyle Normal
    }
    exit 1
}
