from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

connect_args: dict[str, object] = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Importing the service registers its SQLAlchemy session listeners. Keeping this
# beside SessionLocal ensures scanner, API, watcher, and test sessions all apply
# the same multi-version grouping rules.
from app.services import media_versions as _media_versions  # noqa: E402,F401


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
