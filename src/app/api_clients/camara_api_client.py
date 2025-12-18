"""
Provides a reusable, cached HTTP client configured for the CAMARA API.

- Loads configuration from your main `config.py` Settings
- Reuses the same httpx.Client instance across all FastAPI requests
- Recommended for performance and connection reuse
"""

# client.py
from functools import lru_cache
import httpx
from app.config import config as settings
from app.utils.camara_auth import BearerTokenAuth
from app.utils.token_manager import TokenManager
from app.utils.logger import logger


@lru_cache()
def get_token_manager() -> TokenManager:
    '''
    Docstring for get_token_manager
    
    :return: TokenManager instance
    :rtype: TokenManager
    '''
    return TokenManager(
        token_url=settings.aeriOS_TOKEN_URL,
        client_id=settings.aeriOS_CLIENT_ID,
        client_secret=settings.aeriOS_CLIENT_SECRET or None,
        username=settings.aeriOS_USERNAME,
        password=settings.aeriOS_PASSWORD,
        scope=settings.aeriOS_SCOPE or None,
    )


@lru_cache()
def get_camara_client() -> httpx.Client:
    """
    Cached httpx.Client for CAMARA calls.
    Automatically injects Authorization: Bearer <token> using BearerTokenAuth.
    
    This ensures that the same client instance is reused across all FastAPI requests,
    enabling connection pooling and improving performance.

    Returns:
        httpx.Client: Configured and cached HTTP client.
    """
    tm = get_token_manager()
    logger.info("Creating cached CAMARA API client with BearerTokenAuth")
    return httpx.Client(
        base_url=settings.CAMARA_ENDPOINT_URL,
        timeout=10.0,
        auth=BearerTokenAuth(tm),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
