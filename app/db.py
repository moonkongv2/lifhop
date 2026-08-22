from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings


engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(bind=engine)


def check_database_connection() -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return True
