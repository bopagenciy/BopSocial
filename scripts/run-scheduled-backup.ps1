<#
.SYNOPSIS
    Bop Social — Scheduled Daily Backup Wrapper (BS-10A)
.DESCRIPTION
    Runs scheduled backup with safe non-intrusive guards:
    1. Checks if Docker daemon and PostgreSQL container are running.
       - Does NOT start Docker if it is stopped.
    2. Runs PostgreSQL backup script with 30-day retention.
    3. Backs up media volume assets if container running.
    4. Logs operational results and failures to backups/backup.log.
#>
[CmdletBinding()]
param(
    [string]$ProjectRoot = "E:\RECURSOS\ANTIGRAVITY\AgencyOS",
    [int]$RetentionDays = 30
)

$LogDir = Join-Path $ProjectRoot "backups"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "backup.log"

function Log-Message([string]$msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding utf8
}

Log-Message "Starting BopSocial scheduled backup run..."

# Guard 1: Docker daemon availability check (does NOT start Docker)
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Log-Message "SKIPPED: Docker daemon is not running. Scheduled backup will not start Docker automatically."
        exit 0
    }
} catch {
    Log-Message "SKIPPED: Docker CLI not responsive: $_"
    exit 0
}

# Guard 2: Container running check
$container = "agencyos-postgres-1"
$isRunning = docker ps --filter "name=$container" --filter "status=running" --format "{{.Names}}"
if (-not $isRunning) {
    Log-Message "SKIPPED: Container '$container' is not running. Skipping database backup."
    exit 0
}

# Execute PostgreSQL backup
$backupScript = Join-Path $ProjectRoot "scripts\backup-postgres.ps1"
if (-not (Test-Path $backupScript)) {
    Log-Message "ERROR: Backup script not found at $backupScript"
    exit 1
}

try {
    Log-Message "Executing PostgreSQL backup with $RetentionDays days retention..."
    $backupOutput = & powershell.exe -ExecutionPolicy Bypass -File $backupScript -RetentionDays $RetentionDays 2>&1
    if ($LASTEXITCODE -ne 0) {
        Log-Message "ERROR: PostgreSQL backup failed: $($backupOutput -join ' ')"
        exit 1
    } else {
        Log-Message "SUCCESS: $($backupOutput -join ' ')"
    }
} catch {
    Log-Message "ERROR: Exception during database backup: $_"
    exit 1
}

# Persistent media backup (tar from agencyos-backend-1 media volume if running)
$backendContainer = "agencyos-backend-1"
$isBackendRunning = docker ps --filter "name=$backendContainer" --filter "status=running" --format "{{.Names}}"
if ($isBackendRunning) {
    try {
        $MediaBackupDir = Join-Path $ProjectRoot "backups\media"
        if (-not (Test-Path $MediaBackupDir)) { New-Item -ItemType Directory -Path $MediaBackupDir -Force | Out-Null }
        $MediaTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $MediaFile = Join-Path $MediaBackupDir "media_${MediaTimestamp}.tar.gz"
        docker exec $backendContainer tar -czf /tmp/media_backup.tar.gz -C /app media 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            docker cp "${backendContainer}:/tmp/media_backup.tar.gz" $MediaFile
            docker exec $backendContainer rm -f /tmp/media_backup.tar.gz 2>$null | Out-Null
            if (Test-Path $MediaFile) {
                $MediaHash = (Get-FileHash -Path $MediaFile -Algorithm SHA256).Hash.ToLowerInvariant()
                "$MediaHash  $(Split-Path -Leaf $MediaFile)" | Out-File -FilePath "${MediaFile}.sha256" -Encoding ascii
                Log-Message "SUCCESS: Media backup created -> $MediaFile (sha256=$MediaHash)"
                # Prune media backups > RetentionDays
                $Cutoff = (Get-Date).AddDays(-$RetentionDays)
                Get-ChildItem -Path $MediaBackupDir -Filter "media_*.tar.gz" | Where-Object { $_.LastWriteTime -lt $Cutoff } | ForEach-Object {
                    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
                    Remove-Item "$($_.FullName).sha256" -Force -ErrorAction SilentlyContinue
                    Log-Message "  Pruned expired media backup: $($_.Name)"
                }
            }
        }
    } catch {
        Log-Message "WARNING: Media backup encountered non-fatal error: $_"
    }
}

Log-Message "Scheduled backup completed successfully."
exit 0
