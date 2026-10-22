# ============================================================================
#  Bop Social — Canonical Local Startup Script (BS-INFRA-1)
# ============================================================================
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# 1. Resolve repository root safely
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
Set-Location $RepoRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Starting Bop Social (AgencyOS) Local Stack      " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Repository root: $RepoRoot"

# 2. Verify Docker daemon is running
Write-Host "`n[1/6] Verifying Docker daemon..." -ForegroundColor Yellow
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Docker daemon is not responding."
    }
    Write-Host "  Docker daemon is running." -ForegroundColor Green
} catch {
    Write-Error "Docker is not running or not accessible. Please start Docker Desktop."
    exit 1
}

# 3. Verify frontend/package.json exists
$FrontendPkg = Join-Path $RepoRoot "frontend\package.json"
if (-not (Test-Path $FrontendPkg)) {
    Write-Error "frontend/package.json not found at $FrontendPkg"
    exit 1
}

# 4. Build frontend on HOST (Do not run inside Docker to avoid WSL memory exhaustion)
Write-Host "`n[2/6] Building Bop Social React frontend on host..." -ForegroundColor Yellow
Push-Location (Join-Path $RepoRoot "frontend")
try {
    $env:CI = "true"
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend build failed with exit code $LASTEXITCODE"
    }
    Write-Host "  Frontend build succeeded. Static assets ready in frontend/build." -ForegroundColor Green
} catch {
    Pop-Location
    Write-Error "Frontend compilation failed: $_"
    exit 1
}
Pop-Location

# 5. Start infrastructure databases (postgres & redis)
Write-Host "`n[3/6] Starting databases (postgres, redis)..." -ForegroundColor Yellow
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start postgres and redis."
    exit 1
}

# 6. Wait for database health
Write-Host "  Waiting for postgres and redis to be healthy..."
$dbTimeout = 30
$elapsed = 0
while ($elapsed -lt $dbTimeout) {
    $pgHealth = docker inspect --format='{{json .State.Health.Status}}' agencyos-postgres-1 2>$null
    $rdHealth = docker inspect --format='{{json .State.Health.Status}}' agencyos-redis-1 2>$null
    if ($pgHealth -match "healthy" -and $rdHealth -match "healthy") {
        Write-Host "  Databases are healthy." -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 2
    $elapsed += 2
}

# 7. Build local images deterministically
Write-Host "`n[4/6] Building Bop Social local runtime images..." -ForegroundColor Yellow
docker compose build
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker compose build failed."
    exit 1
}

# 8. Start backend service and wait for health
Write-Host "`n[5/6] Starting backend service..." -ForegroundColor Yellow
docker compose up -d backend
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start backend service."
    exit 1
}

Write-Host "  Waiting for backend service to become healthy..."
$beTimeout = 60
$elapsed = 0
$backendReady = $false
while ($elapsed -lt $beTimeout) {
    $beHealth = docker inspect --format='{{json .State.Health.Status}}' agencyos-backend-1 2>$null
    if ($beHealth -match "healthy") {
        $backendReady = $true
        Write-Host "  Backend service is healthy." -ForegroundColor Green
        break
    }
    Start-Sleep -Seconds 3
    $elapsed += 3
}

if (-not $backendReady) {
    Write-Warning "Backend healthcheck timed out after ${beTimeout}s, proceeding with caution..."
}

# 9. Start frontend, worker, and beat
Write-Host "`n[6/6] Starting frontend, celery worker, and beat..." -ForegroundColor Yellow
docker compose up -d frontend worker beat
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to start frontend and background workers."
    exit 1
}

# 10. Status and URLs
Write-Host "`n==================================================" -ForegroundColor Green
Write-Host "  Bop Social Stack is UP and RUNNING!             " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
docker compose ps

Write-Host "`nService Endpoints:" -ForegroundColor Cyan
Write-Host "  Bop Social Frontend: http://localhost:3010" -ForegroundColor White
Write-Host "  Backend Direct API:  http://localhost:8010 (or 8000 inside Docker)" -ForegroundColor White
Write-Host "  Django Admin:        http://localhost:8010/admin/" -ForegroundColor White
Write-Host "==================================================" -ForegroundColor Cyan
