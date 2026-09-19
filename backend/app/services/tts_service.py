import logging
import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core.exceptions import ProviderError

logger = logging.getLogger(__name__)

_OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

class TTSService:
    def __init__(self, http_client: httpx.AsyncClient):
        self._http = http_client

    def is_available(self) -> bool:
        return settings.TTS_ENABLED and settings.LLM_API_KEY is not None

    def get_status(self) -> dict:
        return {
            "available": self.is_available(),
            "provider": "openai" if self.is_available() else None,
            "voice": settings.TTS_VOICE if self.is_available() else "",
        }

    async def synthesize(self, text: str) -> bytes:
        if not self.is_available():
            raise ProviderError("TTS is not enabled or LLM_API_KEY is missing")

        if len(text) > settings.TTS_MAX_CHARS:
            logger.warning(f"TTS text too long: {len(text)} > {settings.TTS_MAX_CHARS}")
            text = text[:settings.TTS_MAX_CHARS]
            
        key = settings.LLM_API_KEY.get_secret_value() # type: ignore
        
        payload = {
            "model": settings.TTS_MODEL,
            "input": text,
            "voice": settings.TTS_VOICE,
            "response_format": "mp3",
        }
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

        try:
            # We use a slightly longer timeout for TTS specifically.
            response = await self._http.post(
                _OPENAI_TTS_URL,
                json=payload,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI TTS HTTP error: {e.response.text}")
            raise ProviderError(f"TTS provider returned status {e.response.status_code}") from e
        except httpx.RequestError as e:
            logger.error(f"OpenAI TTS Request error: {str(e)}")
            raise ProviderError(f"TTS request failed: {str(e)}") from e
