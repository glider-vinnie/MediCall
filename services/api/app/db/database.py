from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Small synchronous SQLAlchemy wrapper used by the FastAPI service."""

    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(bind=self.engine, autocommit=False, autoflush=False, expire_on_commit=False)

    def session(self) -> Generator[Session, None, None]:
        db = self.session_factory()
        try:
            yield db
        finally:
            db.close()


def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_schema(database: Database) -> None:
    from app.db.models import Base

    Base.metadata.create_all(bind=database.engine)
