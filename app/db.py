"""One JSON document per farmer preserves the shared data contract."""
from collections.abc import Generator
from pathlib import Path

from fastapi import Request
from sqlalchemy import JSON, String, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.schemas import FarmerProfile


class Base(DeclarativeBase):
    pass


class FarmerRow(Base):
    __tablename__ = "farmers"
    farmer_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False)

    def as_profile(self) -> FarmerProfile:
        return FarmerProfile.model_validate(self.profile)


def create_database(settings: Settings):
    url = make_url(settings.database_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("This MVP supports SQLite only")
    if url.database and url.database != ":memory:":
        path = Path(url.database)
        if not path.is_absolute():
            path = settings.project_dir / path
        path.parent.mkdir(parents=True, exist_ok=True)
        url = url.set(database=str(path))
    options = {"connect_args": {"check_same_thread": False}}
    if url.database in (None, "", ":memory:"):
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(engine, expire_on_commit=False)


def get_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session
