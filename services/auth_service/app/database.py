import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# Read database settings from environment variables.
DB_USER = os.getenv("AUTH_DB_USER")
DB_PASSWORD = os.getenv("AUTH_DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "mysql")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("AUTH_DB_NAME", "shopease_auth_db")


# Build the MySQL connection URL.
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"f"@{DB_HOST}:{DB_PORT}/{DB_NAME}")


# Create SQLAlchemy engine.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# Create database sessions.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base class for SQLAlchemy models.
Base = declarative_base()


# Dependency for FastAPI routes.
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()