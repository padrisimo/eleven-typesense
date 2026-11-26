from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import close_db, init_db
from .routes import generate, health, search, sounds


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Soundseek API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(sounds.router)
    app.include_router(generate.router)
    return app


app = create_app()
