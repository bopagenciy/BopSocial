# ============================================================================
#  Bop Social — Canonical Local Stop Script (BS-INFRA-1)
# ============================================================================
[CmdletBinding()]
param(
    [switch]$Down = $false
)

$ErrorActionPreference = "Stop"

# 1. Resolve repository root safely
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Stopping Bop Social (AgencyOS) Local Stack      " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Stop ONLY this Compose project; preserve volumes, databases, and other containers
if ($Down) {
    Write-Host "Tearing down containers for AgencyOS (preserving volumes)..." -ForegroundColor Yellow
    docker compose down
} else {
    Write-Host "Stopping containers for AgencyOS (preserving state)..." -ForegroundColor Yellow
    docker compose stop
}

Write-Host "`nAgencyOS stack stopped successfully." -ForegroundColor Green
Write-Host "Persistent data volumes (pgdata, media) remain intact." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
