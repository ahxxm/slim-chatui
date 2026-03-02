import json
import logging
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from typing import Any

from open_webui.env import DATABASE_URL
from sqlalchemy import Dialect, create_engine, MetaData, event, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

log = logging.getLogger(__name__)


class JSONField(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: _T | None, dialect: Dialect) -> Any:
        return json.dumps(value)

    def process_result_value(self, value: _T | None, dialect: Dialect) -> Any:
        if value is not None:
            return json.loads(value)

    def copy(self, **kw: Any) -> Self:
        return JSONField(self.impl.length)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def on_connect(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.close()


event.listen(engine, "connect", on_connect)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
metadata_obj = MetaData()
Base = declarative_base(metadata=metadata_obj)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)


@contextmanager
def get_db_context(db: Session | None = None):
    with get_db() as session:
        yield session


def backup_db() -> str:
    """Create a consistent snapshot of the SQLite database via backup API.
    Returns the path to the temp file. Caller is responsible for cleanup."""
    source = sqlite3.connect(engine.url.database)
    fd, backup_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    dest = sqlite3.connect(backup_path)
    source.backup(dest)
    source.close()
    dest.close()
    return backup_path
