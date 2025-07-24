"""
Provides a reusable, cached HTTP client configured for the CAMARA API.

- Loads configuration from your main `config.py` Settings
- Reuses the same httpx.Client instance across all FastAPI requests
- Recommended for performance and connection reuse
"""

from functools import lru_cache
import httpx
from app.config import config


@lru_cache()
def get_camara_client() -> httpx.Client:
    """
    Returns a cached instance of httpx.Client configured for CAMARA.
    
    This ensures that the same client instance is reused across all FastAPI requests,
    enabling connection pooling and improving performance.

    Returns:
        httpx.Client: Configured and cached HTTP client.
    """
    return httpx.Client(
        base_url=config.CAMARA_ENDPOINT_URL,
        timeout=10.0,
        headers={
            "Content-Type": "application/json"
            # Authorization or other headers here if needed
        })
