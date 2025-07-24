"""
Provides a reusable, cached HTTP client configured for the EaaS Application Repository API.

- Loads configuration from the centralized `config.py`
- Reuses the same httpx.Client instance across FastAPI requests
- Allows calling endpoints like /app_packages/{appPackageId}
"""

from functools import lru_cache
import httpx
from app.config import config


@lru_cache()
def get_app_repo_client() -> httpx.Client:
    """
    Returns a cached instance of httpx.Client configured for the EaaS Application Repository.

    This ensures the same client is reused for efficiency and connection pooling.

    Returns:
        httpx.Client: Configured HTTP client for Application Repository.
    """
    return httpx.Client(
        base_url=config.EAAS_APPLICATION_REPO_URL,
        timeout=10.0,
        headers={
            "Content-Type": "application/json"
            # Add auth headers if needed
        })
