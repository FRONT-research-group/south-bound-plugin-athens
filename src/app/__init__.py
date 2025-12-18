'''
Athens SouthBound Edge Application Management API
'''
from contextlib import asynccontextmanager
from fastapi import FastAPI, __version__
from app.routers import eaas_router
from app.utils.logger import logger
from app.api_clients.camara_api_client import get_camara_client, get_token_manager

# FastAPI object customization
FASTAPI_TITLE = "Athens SouthBound Edge Application Management API"
FASTAPI_DESCRIPTION = "Athens SouthBound Edge Application Management API..."
FASTAPI_VERSION = f"{__version__}"
FASTAPI_DOCS_URL = "/docs"  # Swagger UI (default)
FASTAPI_OPEN_API_URL = "/openapi.json"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """
    Application lifespan handler.

    - Validates aerOS credentials by acquiring an access token once at startup.
    - Initializes the cached CAMARA HTTP client to warm up connection pools.
    """
    # Startup
    token_manager = get_token_manager()
    token_manager.get_token()  # Fail fast if credentials are wrong

    get_camara_client()  # Initialize cached client

    yield

    # Shutdown (optional cleanup)
    # httpx.Client is cached and process-scoped; no explicit close required here


app = FastAPI(title=FASTAPI_TITLE,
              description=FASTAPI_DESCRIPTION,
              version=FASTAPI_VERSION,
              docs_url=FASTAPI_DOCS_URL,
              openapi_url=FASTAPI_OPEN_API_URL)

# Include Routers
app.include_router(eaas_router.router)


@logger.catch
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
