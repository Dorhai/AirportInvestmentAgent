"""POST /api/chat — conversational agent endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatResponse
from app.models.request import ChatRequest

router = APIRouter()

@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    orchestrator = request.app.state.orchestrator
    
    async def _stream():
        async for event in orchestrator.turn_stream(req):
            yield event.render()
            
    return StreamingResponse(_stream(), media_type="text/event-stream")
