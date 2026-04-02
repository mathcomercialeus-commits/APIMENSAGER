import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.core.logging import configure_logging
from app.db.bootstrap import bootstrap_reference_data
from app.models import Base


logger = logging.getLogger(__name__)
STARTUP_DB_MAX_ATTEMPTS = 20
STARTUP_DB_RETRY_SECONDS = 3


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging(settings.debug)
    try:
        logger.info("Inicializando aplicacao. auto_create_tables=%s", settings.auto_create_tables)
        last_error: Exception | None = None

        for attempt in range(1, STARTUP_DB_MAX_ATTEMPTS + 1):
            try:
                logger.info("Tentativa de inicializacao do banco %s/%s", attempt, STARTUP_DB_MAX_ATTEMPTS)
                if settings.auto_create_tables:
                    logger.info("Criando tabelas via metadata.create_all...")
                    async with engine.begin() as connection:
                        await connection.run_sync(Base.metadata.create_all)
                    logger.info("Criacao de tabelas concluida.")

                logger.info("Executando bootstrap_reference_data...")
                async with AsyncSessionLocal() as session:
                    await bootstrap_reference_data(session)
                logger.info("Bootstrap inicial concluido.")
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                logger.exception("Falha na tentativa %s de inicializacao do banco.", attempt)
                if attempt >= STARTUP_DB_MAX_ATTEMPTS:
                    raise
                await asyncio.sleep(STARTUP_DB_RETRY_SECONDS)

        if last_error is not None:
            raise last_error

        yield
    except Exception:
        logger.exception("Falha durante a inicializacao da aplicacao.")
        raise
    finally:
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
