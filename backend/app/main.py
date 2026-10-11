from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import Base, engine
from app import models
from app.routes import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="VerseRAG",
    description="Version-aware document intelligence",
    version="0.1.0",
    lifespan=lifespan,
)
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.include_router(documents_router)


@app.get("/")
def root():
    index_file = Path(__file__).resolve().parents[1] / "frontend-dist" / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "project": "VerseRAG",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {"database": "connected"}


frontend_dist = Path(__file__).resolve().parents[1] / "frontend-dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

# Wrap the complete app so browser requests also receive CORS headers on
# unhandled errors, instead of surfacing them as an opaque "Failed to fetch".
app = CORSMiddleware(
    app,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
