from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter()

class TtsRequest(BaseModel):
    text: str

@router.get("/tts/status")
async def tts_status(request: Request):
    """Returns TTS capability status without exposing secrets."""
    tts_service = request.app.state.tts_service
    return tts_service.get_status()

@router.post("/tts")
async def synthesize_speech(req: TtsRequest, request: Request):
    """
    Converts text to speech using the configured provider.
    Returns audio/mpeg stream.
    """
    tts_service = request.app.state.tts_service
    
    if not tts_service.is_available():
        raise HTTPException(status_code=503, detail="TTS service is unavailable")

    try:
        audio_bytes = await tts_service.synthesize(req.text)
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={"Content-Disposition": 'inline; filename="speech.mp3"'}
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
