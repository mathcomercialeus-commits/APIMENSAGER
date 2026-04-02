from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import configure_logging
from app.db.bootstrap import bootstrap_reference_data
from app.models import Base


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.debug)

    if settings.auto_create_tables:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await bootstrap_reference_data(session)

    yield

    await engine.dispose()


app = FastAPI(title=settings.project_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
