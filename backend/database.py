from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from core import load_config

CONFIG = load_config()
SQLALCHEMY_DATABASE_URL = CONFIG.db_url

engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
        if SQLALCHEMY_DATABASE_URL.startswith("sqlite")
        else {},
    )
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
