from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine
from app import models
from app.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables during initial development.
    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title="ShopEase Authentication Service",
    description="Handles user registration, login and JWT authentication.",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(auth_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to ShopEase Authentication Service"
    }


@app.get("/health")
def health_check():
    return {
        "service": "authentication",
        "status": "healthy"
    }


@app.get("/health/database")
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "service": "authentication",
            "database": "connected",
            "status": "healthy"
        }

    except Exception:
        return {
            "service": "authentication",
            "database": "disconnected",
            "status": "unhealthy"
        }