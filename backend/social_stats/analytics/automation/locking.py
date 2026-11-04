"""
Single-flight concurrency locking for BS-6A Intelligence Automation.
Guarantees mutually exclusive execution for the same tenant-period-version
using PostgreSQL session-level advisory locks with fallback for in-memory/test backends.
"""
import logging
from typing import Optional

from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


class ConcurrencyLockError(RuntimeError):
    """Raised when a single-flight execution lock cannot be acquired."""
    pass


class SingleFlightLock:
    """
    Acquires and releases a single-flight concurrency lock.
    In PostgreSQL, uses pg_try_advisory_lock / pg_advisory_unlock on a 64-bit int
    derived from the first 15 hex digits of the execution_identity.
    In SQLite / fallback, uses atomic cache lock.
    """
    def __init__(self, execution_identity: str, timeout_seconds: int = 3600):
        self.execution_identity = execution_identity
        self.timeout_seconds = timeout_seconds
        # Derive signed 64-bit int from first 15 hex characters: [0 .. 16^15 - 1]
        self.lock_id = int(execution_identity[:15], 16)
        self.acquired = False

    def acquire(self) -> bool:
        if connection.vendor == "postgresql":
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_try_advisory_lock(%s);", [self.lock_id])
                    row = cursor.fetchone()
                    self.acquired = bool(row and row[0])
            except Exception as e:
                logger.warning("Postgres advisory lock failed: %s; falling back to cache lock", e)
                self.acquired = self._acquire_cache_lock()
        else:
            self.acquired = self._acquire_cache_lock()

        return self.acquired

    def release(self) -> bool:
        if not self.acquired:
            return True

        success = True
        if connection.vendor == "postgresql":
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_unlock(%s);", [self.lock_id])
                    row = cursor.fetchone()
                    success = bool(row and row[0])
            except Exception as e:
                logger.warning("Postgres advisory unlock error: %s", e)
                success = False

        self._release_cache_lock()
        self.acquired = False
        return success

    def _acquire_cache_lock(self) -> bool:
        key = f"single_flight_lock:{self.execution_identity}"
        return bool(cache.add(key, "1", timeout=self.timeout_seconds))

    def _release_cache_lock(self) -> None:
        key = f"single_flight_lock:{self.execution_identity}"
        cache.delete(key)

    def __enter__(self):
        if not self.acquire():
            raise ConcurrencyLockError(
                f"Active execution lock already held for execution identity: {self.execution_identity}"
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
