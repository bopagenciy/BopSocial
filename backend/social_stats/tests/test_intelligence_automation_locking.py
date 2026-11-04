"""
Unit Tests for BS-6A Single-Flight Concurrency Locking (Test Matrix AS).
Tests lock acquisition, mutual exclusion on identical execution identity,
independent locks for different tenants or periods, and clean release.
"""
from datetime import date
from django.test import TestCase

from social_stats.analytics.automation.identity import compute_execution_identity
from social_stats.analytics.automation.locking import SingleFlightLock, ConcurrencyLockError


class IntelligenceAutomationLockingTests(TestCase):
    def setUp(self):
        self.client_1 = 101
        self.client_2 = 202
        self.period_1_start = date(2026, 9, 1)
        self.period_1_end = date(2026, 9, 30)
        self.period_2_start = date(2026, 10, 1)
        self.period_2_end = date(2026, 10, 31)

        self.ident_1 = compute_execution_identity(self.client_1, self.period_1_start, self.period_1_end)
        self.ident_diff_client = compute_execution_identity(self.client_2, self.period_1_start, self.period_1_end)
        self.ident_diff_period = compute_execution_identity(self.client_1, self.period_2_start, self.period_2_end)

    def test_single_flight_lock_acquisition_and_release(self):
        """First execution acquires lock cleanly; release frees the lock."""
        lock = SingleFlightLock(self.ident_1)
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.acquired)

        # Release
        self.assertTrue(lock.release())
        self.assertFalse(lock.acquired)

        # Can acquire again after release
        lock2 = SingleFlightLock(self.ident_1)
        self.assertTrue(lock2.acquire())
        lock2.release()

    def test_concurrent_same_identity_blocked(self):
        """A second concurrent lock attempt on the identical execution identity is blocked across sessions."""
        from django.db import connection, connections

        lock1 = SingleFlightLock(self.ident_1)
        self.assertTrue(lock1.acquire())

        if connection.vendor == "postgresql":
            # In PostgreSQL, advisory locks are session-scoped. A second database connection (simulating Worker 2)
            # must fail to acquire the same lock.
            conn2 = connections.create_connection("default")
            try:
                with conn2.cursor() as cur:
                    cur.execute("SELECT pg_try_advisory_lock(%s);", [lock1.lock_id])
                    acquired_by_worker2 = cur.fetchone()[0]
                    self.assertFalse(acquired_by_worker2)
            finally:
                conn2.close()
        else:
            lock2 = SingleFlightLock(self.ident_1)
            self.assertFalse(lock2.acquire())

        lock1.release()

    def test_different_tenants_acquire_locks_concurrently(self):
        """Two different tenants can execute concurrently without blocking each other."""
        lock_client1 = SingleFlightLock(self.ident_1)
        lock_client2 = SingleFlightLock(self.ident_diff_client)

        self.assertTrue(lock_client1.acquire())
        self.assertTrue(lock_client2.acquire())

        lock_client1.release()
        lock_client2.release()

    def test_different_periods_acquire_locks_concurrently(self):
        """Same tenant executing different reporting periods can acquire locks concurrently."""
        lock_p1 = SingleFlightLock(self.ident_1)
        lock_p2 = SingleFlightLock(self.ident_diff_period)

        self.assertTrue(lock_p1.acquire())
        self.assertTrue(lock_p2.acquire())

        lock_p1.release()
        lock_p2.release()

    def test_lock_released_on_exception_in_context_manager(self):
        """Context manager guarantees release even when an exception is raised inside the block."""
        try:
            with SingleFlightLock(self.ident_1):
                raise RuntimeError("Simulated failure inside locked block")
        except RuntimeError:
            pass

        # Lock should now be free
        lock = SingleFlightLock(self.ident_1)
        self.assertTrue(lock.acquire())
        lock.release()
