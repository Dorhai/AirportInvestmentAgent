from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class Health(BaseModel):
    status: str

@router.get("/health", response_model=Health)
async def health_check():
    return Health(status="ok")