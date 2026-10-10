import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# On Vercel the project root is read-only; only /tmp is writable.
# Fall back to /tmp when the default relative path is used.
_default_db = (
    "sqlite:////tmp/repurposekit.db"
    if os.getenv("VERCEL")
    else "sqlite:///./repurposekit.db"
)
DATABASE_URL = os.getenv("DATABASE_URL", _default_db)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
