from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app import models
from app.database import Base, engine
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="ShopEase Product Service",
    description="Manages product catalog, categories and inventory.",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(router)


@app.get("/")
def home():
    return {
        "message": "Welcome to ShopEase Product Service"
    }


@app.get("/health")
def health():
    return {
        "service": "product",
        "status": "healthy"
    }


@app.get("/health/database")
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "status": "healthy"
        }

    except Exception:
        return {
            "database": "disconnected",
            "status": "unhealthy"
        }