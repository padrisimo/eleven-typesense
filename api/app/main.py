from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import get_settings
from .db import init_db, close_db
from .routes import health, search, sounds, generate


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Soundsnap API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(search.router)
    app.include_router(sounds.router)
    app.include_router(generate.router)
    return app


app = create_app()
