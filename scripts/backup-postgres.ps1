<#
.SYNOPSIS
    Bop Social — PostgreSQL Backup & Integrity Verification (BS-9D)
.DESCRIPTION
    Creates a timestamped custom-format pg_dump of the canonical `socialstats`
    database inside Docker (`agencyos-postgres-1`), writes a SHA-256 checksum,
    verifies archive integrity with `pg_restore --list`, and enforces retention.
#>
[CmdletBinding()]
param(
    [string]$ContainerName = "agencyos-postgres-1",
    [string]$DbName = "socialstats",
    [string]$DbUser = "socialstats",
    [string]$BackupDir = "",
    [int]$RetentionDays = 14
)

$ErrorActionPreference = "Stop"

if (-not $BackupDir) {
    $BackupDir = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path (Split-Path -Parent $PSScriptRoot) "backups\postgres" }
}
if ($env:BACKUP_RETENTION_DAYS) {
    $RetentionDays = [int]$env:BACKUP_RETENTION_DAYS
}

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupDir "${DbName}_${Timestamp}.dump"
$ChecksumFile = "${BackupFile}.sha256"

if (Test-Path $BackupFile) {
    Write-Error "Refusing to overwrite existing backup file: $BackupFile"
    exit 1
}

Write-Host "[1/4] Checking PostgreSQL container '$ContainerName'..."
$PgReady = docker exec $ContainerName pg_isready -U $DbUser -d $DbName 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "PostgreSQL container '$ContainerName' is not ready: $PgReady"
    exit 1
}

Write-Host "[2/4] Creating timestamped pg_dump -> $BackupFile"
$TempContainerPath = "/tmp/${DbName}_${Timestamp}.dump"
docker exec $ContainerName pg_dump -U $DbUser -d $DbName --format=custom --no-owner --no-acl -f $TempContainerPath
if ($LASTEXITCODE -ne 0) {
    docker exec $ContainerName rm -f $TempContainerPath 2>$null | Out-Null
    Write-Error "pg_dump failed with exit code $LASTEXITCODE"
    exit 1
}

docker cp "${ContainerName}:${TempContainerPath}" $BackupFile
$CopyExit = $LASTEXITCODE
docker exec $ContainerName rm -f $TempContainerPath 2>$null | Out-Null
if ($CopyExit -ne 0 -or -not (Test-Path $BackupFile)) {
    Write-Error "Failed to copy backup out of container."
    exit 1
}

$SizeBytes = (Get-Item $BackupFile).Length
if ($SizeBytes -le 0) {
    Remove-Item $BackupFile -Force -ErrorAction SilentlyContinue
    Write-Error "Backup file is empty (0 bytes)."
    exit 1
}

Write-Host "[3/4] Verifying backup integrity & writing SHA-256 checksum..."
$Hash = (Get-FileHash -Path $BackupFile -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $(Split-Path -Leaf $BackupFile)" | Out-File -FilePath $ChecksumFile -Encoding ascii

$TempVerify = "/tmp/verify_${Timestamp}.dump"
docker cp $BackupFile "${ContainerName}:${TempVerify}"
$ListOut = docker exec $ContainerName pg_restore --list $TempVerify 2>&1
$VerifyExit = $LASTEXITCODE
docker exec $ContainerName rm -f $TempVerify 2>$null | Out-Null
if ($VerifyExit -ne 0) {
    Write-Error "pg_restore --list integrity verification failed: $ListOut"
    exit 1
}

Write-Host "[4/4] Enforcing retention policy ($RetentionDays days)..."
if ($RetentionDays -gt 0) {
    $Cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem -Path $BackupDir -Filter "${DbName}_*.dump" | Where-Object { $_.LastWriteTime -lt $Cutoff } | ForEach-Object {
        $Sha = "$($_.FullName).sha256"
        Remove-Item $_.FullName -Force
        if (Test-Path $Sha) { Remove-Item $Sha -Force }
        Write-Host "  Pruned expired backup: $($_.Name)"
    }
}

Write-Host "BACKUP PASS: $BackupFile ($SizeBytes bytes, sha256=$Hash)"
