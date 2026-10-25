from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por request."""
    with Session(engine) as session:
        yield session


def get_engine() -> Engine:
    """Dependencia de FastAPI: el procesamiento en segundo plano abre sus propias sesiones."""
    return engine
