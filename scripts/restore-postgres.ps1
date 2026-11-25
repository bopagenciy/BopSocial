<#
.SYNOPSIS
    Bop Social — PostgreSQL Isolated Restore & Verification (BS-9D)
.DESCRIPTION
    Verifies SHA-256 checksum and restores a `.dump` backup into an isolated
    target database. Refuses to overwrite canonical `socialstats` unless
    explicitly overridden. Supports `-IsolatedVerifyOnly` to test recovery in a
    temporary database and drop it afterwards.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile,
    [string]$ContainerName = "agencyos-postgres-1",
    [string]$DbUser = "socialstats",
    [string]$TargetDb = "",
    [switch]$IsolatedVerifyOnly,
    [switch]$AllowOverwriteCanonical
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BackupFile)) {
    Write-Error "Backup file not found: $BackupFile"
    exit 1
}

$ChecksumFile = "${BackupFile}.sha256"
if (Test-Path $ChecksumFile) {
    $ExpectedHash = ((Get-Content $ChecksumFile -Raw).Trim().Split(" ")[0]).ToLowerInvariant()
    $ActualHash = (Get-FileHash -Path $BackupFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ExpectedHash -ne $ActualHash) {
        Write-Error "Checksum mismatch! Expected=$ExpectedHash Actual=$ActualHash"
        exit 1
    }
    Write-Host "Checksum OK: $ActualHash"
}

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if ($IsolatedVerifyOnly) {
    $TargetDb = "verify_restore_${Timestamp}"
}

if ([string]::IsNullOrWhiteSpace($TargetDb)) {
    Write-Error "Specify -TargetDb <name> or -IsolatedVerifyOnly."
    exit 1
}

if ($TargetDb -eq "socialstats" -and -not $AllowOverwriteCanonical) {
    Write-Error "SAFETY BLOCK: Refusing to restore over canonical 'socialstats' database without -AllowOverwriteCanonical."
    exit 1
}

$TempRestorePath = "/tmp/restore_${Timestamp}.dump"
docker cp $BackupFile "${ContainerName}:${TempRestorePath}"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to copy backup into container."
    exit 1
}

try {
    Write-Host "Creating target database '$TargetDb'..."
    docker exec $ContainerName psql -U $DbUser -d postgres -c "CREATE DATABASE $TargetDb;" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create target database '$TargetDb'."
    }

    Write-Host "Restoring archive into '$TargetDb'..."
    docker exec $ContainerName pg_restore -U $DbUser -d $TargetDb --no-owner --no-acl $TempRestorePath
    if ($LASTEXITCODE -ne 0) {
        throw "pg_restore failed into '$TargetDb'."
    }

    $ClientCount = (docker exec $ContainerName psql -U $DbUser -d $TargetDb -t -A -c "SELECT count(*) FROM social_stats_client;").Trim()
    $UserCount = (docker exec $ContainerName psql -U $DbUser -d $TargetDb -t -A -c "SELECT count(*) FROM auth_user;").Trim()
    $TableCount = (docker exec $ContainerName psql -U $DbUser -d $TargetDb -t -A -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';").Trim()
    Write-Host "RESTORE VERIFIED ($TargetDb): tables=$TableCount users=$UserCount clients=$ClientCount"
}
finally {
    docker exec $ContainerName rm -f $TempRestorePath 2>$null | Out-Null
    if ($IsolatedVerifyOnly) {
        Write-Host "Cleaning up temporary verification database '$TargetDb'..."
        docker exec $ContainerName psql -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS $TargetDb;" | Out-Null
    }
}
