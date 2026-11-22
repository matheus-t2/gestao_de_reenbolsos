import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nexus.db")
_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if _is_sqlite else {})


@event.listens_for(Engine, "connect")
def _sqlite_fk(dbapi_conn, _):
    if _is_sqlite:
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
