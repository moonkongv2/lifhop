from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine)

def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session

def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
