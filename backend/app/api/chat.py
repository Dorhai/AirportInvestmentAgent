"""POST /api/chat — conversational agent endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatResponse, Confirmation
from app.models.request import ChatRequest

router = APIRouter()

@router.post("/chat")
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    orchestrator = request.app.state.orchestrator
    
    async def _stream():
        async for event in orchestrator.turn_stream(req):
            yield event.render()
            
    return StreamingResponse(_stream(), media_type="text/event-stream")

@router.get("/chat/schema", response_model=ChatResponse, include_in_schema=True)
async def chat_schema() -> ChatResponse:
    """Dummy endpoint to force ChatResponse into the OpenAPI schema."""
    pass

@router.get("/chat/schema/confirmation", response_model=Confirmation, include_in_schema=True)
async def confirmation_schema() -> Confirmation:
    pass
