# Start MCP agent-tools server (Docker)
# Usage: .\scripts\start_mcp.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot
Write-Host "Building and starting MCP server on http://localhost:8765/mcp ..."
try {
    docker compose -f docker/docker-compose.yml up -d --build
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed" }
} catch {
    Write-Host "Docker unavailable — starting local MCP server instead."
    Write-Host "Run scripts/run_mcp_local.ps1 in a separate terminal, then re-run this script."
    exit 1
}

Write-Host "Waiting for MCP server..."
Start-Sleep -Seconds 5

Write-Host "Running MCP connectivity test..."
& "$ProjectRoot\venv\Scripts\python.exe" "$ProjectRoot\scripts\test_mcp.py"
