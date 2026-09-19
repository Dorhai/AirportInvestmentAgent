"""Inbound chat request model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str = Field(default="default")
    voice_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Speech-recognition confidence (0-1). None means typed input.",
    )
