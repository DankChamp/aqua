from fastapi import APIRouter
from pydantic import BaseModel

from core import voice_service
from voice.tts import Speaker

router = APIRouter(prefix="/voice", tags=["voice"])


class SayRequest(BaseModel):
    text: str
    interrupt: bool = True
    max_chars: int = 4200


@router.post("/say")
def say(payload: SayRequest):
    spoken = voice_service.say(
        payload.text,
        interrupt=payload.interrupt,
        max_chars=payload.max_chars,
    )
    return {"ok": True, "spoken": spoken}


@router.post("/stop")
def stop():
    voice_service.stop()
    return {"ok": True}


@router.post("/start")
def start():
    return voice_service.start()


@router.get("/status")
def status():
    return voice_service.status()


@router.get("/voices")
def voices():
    return Speaker.list_voices()
