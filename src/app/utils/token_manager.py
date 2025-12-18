# token_manager.py
import time
import threading
import httpx
from app.utils.logger import logger


class TokenManager:
    """
    Fetches and caches a Keycloak access token (password grant) and refreshes it when expired.
    Thread-safe for use with FastAPI + cached httpx.Client.
    """

    def __init__(
        self,
        token_url: str,
        client_id: str,
        username: str,
        password: str,
        client_secret: str | None = None,
        scope: str | None = None,
        timeout: float = 10.0,
        refresh_skew_seconds: int = 30,
    ):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.scope = scope
        self.timeout = timeout
        self.refresh_skew_seconds = refresh_skew_seconds

        self._lock = threading.Lock()
        self._access_token: str | None = None
        self._expires_at: float = 0.0  # epoch seconds

    def _is_valid(self) -> bool:
        return self._access_token is not None and time.time() < (
            self._expires_at - self.refresh_skew_seconds)

    def get_token(self) -> str:
        """
        Return a valid access token, refreshing it if needed.
        """
        if self._is_valid():
            return self._access_token  # type: ignore[return-value]

        with self._lock:
            if self._is_valid():
                return self._access_token  # type: ignore[return-value]

            self._refresh()
            return self._access_token  # type: ignore[return-value]

    def _refresh(self) -> None:
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "username": self.username,
            "password": self.password,
        }
        if self.client_secret:
            data["client_secret"] = self.client_secret
        if self.scope:
            data["scope"] = self.scope

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.token_url, data=data, headers=headers)

        if resp.status_code != 200:
            # surface useful diagnostics but avoid printing passwords
            raise RuntimeError(
                f"Token request failed ({resp.status_code}): {resp.text}")

        payload = resp.json()
        token = payload.get("access_token")
        expires_in = payload.get("expires_in", 60)

        if not token:
            raise RuntimeError(
                f"Token response missing access_token: {payload}")

        self._access_token = token
        self._expires_at = time.time() + float(expires_in)
