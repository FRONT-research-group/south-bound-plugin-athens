'''
Athens SouthBound Edge Application Management API
'''
from fastapi import FastAPI, __version__
from app.routers import eaas_router
from app.utils.logger import logger

# FastAPI object customization
FASTAPI_TITLE = "Athens SouthBound Edge Application Management API"
FASTAPI_DESCRIPTION = "Athens SouthBound Edge Application Management API..."
FASTAPI_VERSION = f"{__version__}"
FASTAPI_DOCS_URL = "/docs"  # Swagger UI (default)
FASTAPI_OPEN_API_URL = "/openapi.json"

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
