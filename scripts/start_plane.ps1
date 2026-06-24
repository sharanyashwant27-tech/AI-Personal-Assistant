# Start Plane — Python API + Vite UI
# Usage: .\scripts\start_plane.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

Set-Location $Root

Write-Host "Installing Python deps..."
& "$Root\venv\Scripts\pip.exe" install -r requirements.txt -q

Set-Location "$Root\apps\plane"
if (-not (Test-Path node_modules)) {
    Write-Host "Installing UI deps..."
    npm install
}
if (-not (Test-Path dist\index.html)) {
    Write-Host "Building UI..."
    npm run build
}

Write-Host "Starting API + UI on http://127.0.0.1:8787 ..."
$api = Start-Process -FilePath "$Root\venv\Scripts\python.exe" `
    -ArgumentList "src/main.py", "serve" `
    -WorkingDirectory $Root `
    -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 2
Start-Process "http://127.0.0.1:8787"
Write-Host "Plane is running. Press Ctrl+C to stop (API runs in background)."
Set-Location $Root
while ($api -and -not $api.HasExited) { Start-Sleep -Seconds 2 }

if ($api -and -not $api.HasExited) {
    Stop-Process -Id $api.Id -Force -ErrorAction SilentlyContinue
}
