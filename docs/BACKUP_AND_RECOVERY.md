# Bop Social — PostgreSQL Backup & Recovery Runbook

## 1. Automated & Manual Backups
Run the backup script against the canonical Docker PostgreSQL container (`agencyos-postgres-1`, database `socialstats`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/backup-postgres.ps1
```

Configurable parameters / environment variables:
- `BACKUP_DIR` (default: `./backups/postgres`)
- `BACKUP_RETENTION_DAYS` (default: `14`)

Each run produces:
- `<BACKUP_DIR>/socialstats_YYYYMMDD_HHMMSS.dump` (PostgreSQL custom archive)
- `<BACKUP_DIR>/socialstats_YYYYMMDD_HHMMSS.dump.sha256` (integrity hash)
- Runs `pg_restore --list` to verify archive readability before completing.

## 2. Automated Scheduling (Windows Task Scheduler)
Schedule a daily run at 02:00 AM:
- Program/script: `powershell.exe`
- Arguments: `-NoProfile -ExecutionPolicy Bypass -File "E:\RECURSOS\ANTIGRAVITY\AgencyOS\scripts\backup-postgres.ps1"`

## 3. Isolated Recovery Verification
Test any backup in a temporary database without touching `socialstats`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore-postgres.ps1 -BackupFile .\backups\postgres\socialstats_YYYYMMDD_HHMMSS.dump -IsolatedVerifyOnly
```

## 4. Disaster Recovery Restore
To restore into a fresh database (e.g. `socialstats_recovered`):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/restore-postgres.ps1 -BackupFile .\backups\postgres\socialstats_YYYYMMDD_HHMMSS.dump -TargetDb socialstats_recovered
```
