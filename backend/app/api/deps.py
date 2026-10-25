from typing import Annotated

from fastapi import Depends
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db.session import get_engine, get_session

SessionDep = Annotated[Session, Depends(get_session)]
EngineDep = Annotated[Engine, Depends(get_engine)]
