import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

from open_webui.env import (
    DATABASE_URL,
    DATABASE_ENABLE_SESSION_SHARING,
)
from sqlalchemy import Dialect, create_engine, MetaData, event, types
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker, Session
from sqlalchemy.sql.type_api import _T
from typing_extensions import Self

log = logging.getLogger(__name__)


class JSONField(types.TypeDecorator):
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Optional[_T], dialect: Dialect) -> Any:
        return json.dumps(value)

    def process_result_value(self, value: Optional[_T], dialect: Dialect) -> Any:
        if value is not None:
            return json.loads(value)

    def copy(self, **kw: Any) -> Self:
        return JSONField(self.impl.length)


engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def on_connect(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


event.listen(engine, "connect", on_connect)

SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)
metadata_obj = MetaData()
Base = declarative_base(metadata=metadata_obj)
ScopedSession = scoped_session(SessionLocal)


def get_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = contextmanager(get_session)


@contextmanager
def get_db_context(db: Optional[Session] = None):
    if isinstance(db, Session) and DATABASE_ENABLE_SESSION_SHARING:
        yield db
    else:
        with get_db() as session:
            yield session
