from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_normalized_database_url
import logging

logger = logging.getLogger(__name__)

db_url = get_normalized_database_url()

engine_kwargs = {
    "echo": False,
}

if db_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(db_url, **engine_kwargs)
else:
    # Neon PostgreSQL connection pooling settings with timeout
    engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {"connect_timeout": 4}
    })
    try:
        test_engine = create_engine(db_url, **engine_kwargs)
        with test_engine.connect() as conn:
            pass
        engine = test_engine
    except Exception as e:
        logger.warning(f"Remote PostgreSQL unavailable ({e}). Falling back to local SQLite database: sqlite:///./blood_sos.db")
        engine = create_engine("sqlite:///./blood_sos.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        db.close()
