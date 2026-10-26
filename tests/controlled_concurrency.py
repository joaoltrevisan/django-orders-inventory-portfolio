"""Coordinate real PostgreSQL lock contention instead of guessing with delays."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event

from django.db import close_old_connections, connection, connections


class ControlledConcurrencyMixin:
    def run_contended(
        self, first_operation, second_operation, *, pause_before=None, wait_table=None
    ):
        locked, release = Event(), Event()
        pids = Queue()

        def worker(label, operation):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '10s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put((label, cursor.fetchone()[0]))

                def pause(execute, sql, params, many, context):
                    if label == "first" and pause_before is not None and pause_before(sql):
                        locked.set()
                        if not release.wait(8):
                            raise TimeoutError("The test did not release the first operation.")
                    return execute(sql, params, many, context)

                with connection.execute_wrapper(pause):
                    return operation(locked, release)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                first = pool.submit(worker, "first", first_operation)
                label, first_pid = pids.get(timeout=5)
                self.assertEqual(label, "first")
                self.assertTrue(
                    locked.wait(5), "The first operation did not reach its controlled point."
                )
                second = pool.submit(worker, "second", second_operation)
                label, second_pid = pids.get(timeout=5)
                self.assertEqual(label, "second")
                self.assertNotEqual(first_pid, second_pid)
                deadline = time.monotonic() + 5
                blocked = False
                while time.monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [second_pid])
                        blocked = first_pid in cursor.fetchone()[0]
                    if blocked or second.done():
                        break
                    # Bounded polling observes the DB wait; it does not create the race.
                    time.sleep(0.01)
                self.assertTrue(blocked, "PostgreSQL did not show the expected blocking backend.")
                self.assertFalse(second.done())
                if wait_table:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT query FROM pg_stat_activity WHERE pid=%s", [second_pid]
                        )
                        query = cursor.fetchone()[0]
                    self.assertIn('"' + wait_table + '"', query)
                    self.assertIn("FOR UPDATE", query)
                print(
                    "PostgreSQL contention: "
                    + json.dumps(
                        {
                            "scenario": self._testMethodName,
                            "first_backend_pid": first_pid,
                            "second_backend_pid": second_pid,
                            "blocking_observed": blocked,
                        }
                    ),
                    flush=True,
                )
            finally:
                release.set()
            return first.result(timeout=15), second.result(timeout=15)
