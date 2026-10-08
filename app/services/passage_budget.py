"""One deadline across ranking, counts and bounded alias lookups."""
from contextlib import contextmanager
import time
from fastapi import HTTPException
from sqlalchemy import event


@contextmanager
def search_budget(db, seconds: float = 5):
    connection = db.connection()
    deadline = time.monotonic() + seconds
    def before_statement(conn, cursor, statement, parameters, context, executemany):
        remaining = int((deadline-time.monotonic())*1000)
        if remaining <= 0:
            raise HTTPException(503, "search_timeout")
        # A DBAPI cursor avoids reentering this SQLAlchemy execution hook.
        with conn.connection.cursor() as timer:
            timer.execute("SELECT set_config('statement_timeout', %s, true)", (str(remaining),))
    event.listen(connection, "before_cursor_execute", before_statement)
    try:
        yield
        if time.monotonic() >= deadline:
            raise HTTPException(503, "search_timeout")
    finally:
        event.remove(connection, "before_cursor_execute", before_statement)
