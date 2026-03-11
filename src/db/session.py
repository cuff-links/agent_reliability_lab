"""Database engine and session factory.

When DATABASE_URL is unset (local dev, unit tests), engine and SessionLocal are
None and all persistence calls are silently skipped.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, Session

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    _SessionFactory = sessionmaker(bind=engine)

    @contextmanager
    def SessionLocal() -> Generator[Session, None, None]:  # type: ignore[misc]
        session = _SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

else:
    engine = None  # type: ignore[assignment]
    SessionLocal = None  # type: ignore[assignment]
