from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import Base, engine, get_db
from app import models
from app.routes import router as payment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="ShopEase Payment Service",
    description="Payment processing and transaction tracking",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(payment_router)


@app.get("/")
def home():
    return {
        "service": "ShopEase Payment Service",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/database")
def database_health():
    db = next(get_db())

    try:
        db.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "status": "healthy",
        }

    finally:
        db.close()