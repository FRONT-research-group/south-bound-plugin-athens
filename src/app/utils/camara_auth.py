# camara_auth.py
import httpx
from app.utils.token_manager import TokenManager
from app.utils.logger import logger


class BearerTokenAuth(httpx.Auth):
    """
    httpx auth handler that injects Authorization: Bearer <token>
    and automatically refreshes via TokenManager when needed.
    """

    def __init__(self, token_manager: TokenManager):
        self._tm = token_manager

    def auth_flow(self, request: httpx.Request):
        token = self._tm.get_token()
        # loger.debug("##################################")
        # logger.debug("Injecting Bearer token (first 20 chars): %s", token[:20])
        request.headers["Authorization"] = f"Bearer {token}"
        yield request

