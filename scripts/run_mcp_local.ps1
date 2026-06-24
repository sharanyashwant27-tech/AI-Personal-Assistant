# Run MCP agent-tools server locally (no Docker)
# Usage: .\scripts\run_mcp_local.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot
$env:WORKSPACE_ROOT = $ProjectRoot
$env:PYTHONPATH = $ProjectRoot
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8765"
$env:MCP_TRANSPORT = "streamable-http"

Write-Host "Starting local MCP server at http://127.0.0.1:8765/mcp"
& "$ProjectRoot\venv\Scripts\python.exe" -m mcp_servers.agent_tools
