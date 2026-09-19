"""OpenSky OAuth2 client-credentials token manager."""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/"
    "protocol/openid-connect/token"
)
_REFRESH_MARGIN_S = 60.0


class OpenSkyTokenManager:
    """Caches Bearer tokens; refreshes before expiry (~30 min)."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        *,
        timeout_s: float,
    ) -> None:
        self._http = http
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout_s
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0

    async def bearer_headers(self) -> dict[str, str]:
        token = await self._valid_token()
        return {"Authorization": f"Bearer {token}"}

    async def _valid_token(self) -> str:
        now = time.monotonic()
        if self._token and now < self._expires_at:
            return self._token
        async with self._lock:
            now = time.monotonic()
            if self._token and now < self._expires_at:
                return self._token
            return await self._refresh()

    async def _refresh(self) -> str:
        resp = await self._http.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = float(data.get("expires_in", 1800))
        self._token = token
        self._expires_at = time.monotonic() + max(
            expires_in - _REFRESH_MARGIN_S, 30.0
        )
        logger.debug("OpenSky OAuth token refreshed (expires_in=%s)", expires_in)
        return token


def token_manager_from_settings(
    http: httpx.AsyncClient,
    *,
    timeout_s: float | None = None,
) -> OpenSkyTokenManager | None:
    client_id = settings.OPENSKY_CLIENT_ID
    client_secret = settings.OPENSKY_CLIENT_SECRET
    if client_id is None or client_secret is None:
        return None
    id_val = client_id.get_secret_value().strip()
    sec_val = client_secret.get_secret_value().strip()
    if not id_val or not sec_val:
        return None
    return OpenSkyTokenManager(
        http,
        id_val,
        sec_val,
        timeout_s=timeout_s or settings.HTTP_TIMEOUT_S,
    )
