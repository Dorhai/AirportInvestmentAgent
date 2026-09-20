from unittest.mock import AsyncMock

import pytest
import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.services.tts_service import TTSService

def test_tts_status_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", False)
    
    with TestClient(app) as client:
        response = client.get("/api/tts/status")
        assert response.status_code == 200
        assert response.json() == {"available": False, "provider": None, "voice": ""}

from pydantic import SecretStr

def test_tts_status_available(monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("test_key"))
    
    with TestClient(app) as client:
        response = client.get("/api/tts/status")
        assert response.status_code == 200
        assert response.json() == {"available": True, "provider": "openai", "voice": settings.TTS_VOICE}

def test_tts_synthesize_success(monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("test_key"))

    mock_post = AsyncMock()
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.content = b"fake_audio_content"

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            self.post = mock_post

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)
    
    with TestClient(app) as client:
        # Override the dependency/state in the app for testing?
        # Actually TestClient triggers the lifespan block, which will instantiate the real TTSService
        # But we mock httpx.AsyncClient so it gets the mocked one.
        response = client.post("/api/tts", json={"text": "Hello"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        assert response.content == b"fake_audio_content"

def test_tts_synthesize_disabled(monkeypatch):
    monkeypatch.setattr(settings, "TTS_ENABLED", False)
    
    with TestClient(app) as client:
        response = client.post("/api/tts", json={"text": "Hello"})
        assert response.status_code == 503
        assert response.json() == {"detail": "TTS service is unavailable"}
