# camara_auth.py
import httpx
from app.utils.token_manager import TokenManager


class BearerTokenAuth(httpx.Auth):
    """
    httpx auth handler that injects Authorization: Bearer <token>
    and automatically refreshes via TokenManager when needed.
    """

    def __init__(self, token_manager: TokenManager):
        self._tm = token_manager

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._tm.get_token()}"
        yield request
