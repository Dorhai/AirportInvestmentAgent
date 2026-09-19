from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers.opensky_auth import OpenSkyTokenManager, token_manager_from_settings


@pytest.mark.asyncio
async def test_token_manager_caches_token() -> None:
    http = AsyncMock()
    req = httpx.Request("POST", "https://auth.example/token")
    http.post = AsyncMock(
        return_value=httpx.Response(
            200,
            json={"access_token": "abc123", "expires_in": 1800},
            request=req,
        )
    )
    tm = OpenSkyTokenManager(http, "id", "secret", timeout_s=5.0)
    h1 = await tm.bearer_headers()
    h2 = await tm.bearer_headers()
    assert h1 == {"Authorization": "Bearer abc123"}
    assert h2 == h1
    assert http.post.await_count == 1


@pytest.mark.asyncio
async def test_token_manager_refreshes_after_invalidate() -> None:
    http = AsyncMock()
    req = httpx.Request("POST", "https://auth.example/token")
    http.post = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                json={"access_token": "first", "expires_in": 1800},
                request=req,
            ),
            httpx.Response(
                200,
                json={"access_token": "second", "expires_in": 1800},
                request=req,
            ),
        ]
    )
    tm = OpenSkyTokenManager(http, "id", "secret", timeout_s=5.0)
    await tm.bearer_headers()
    tm.invalidate()
    headers = await tm.bearer_headers()
    assert headers["Authorization"] == "Bearer second"
    assert http.post.await_count == 2


def test_token_manager_from_settings_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.providers.opensky_auth.settings.OPENSKY_CLIENT_ID", None)
    monkeypatch.setattr(
        "app.providers.opensky_auth.settings.OPENSKY_CLIENT_SECRET", None
    )
    http = AsyncMock()
    assert token_manager_from_settings(http) is None
