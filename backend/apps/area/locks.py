"""Process-wide locks for memory-heavy work on a small server."""
from contextlib import contextmanager
import threading
from django.db import connection

_OVERTURE_KEY = 0x5041524F  # 'PARO'; any stable bigint
_local = threading.Lock()


@contextmanager
def overture_capture_lock():
    """One DuckDB Overture scan at a time across web and worker processes (Postgres advisory lock).

    SQLite previews run a single worker, so an in-process lock is enough there.
    """
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [_OVERTURE_KEY])
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_unlock(%s)', [_OVERTURE_KEY])
    else:
        with _local:
            yield
