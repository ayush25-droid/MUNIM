"""POST /api/voice: spoken audio -> transcript -> same handling as /api/chat.

Prototype feature on a branch (see PROGRESS.md's "voice is cut" decision) -- doesn't
touch the frozen two-call scan/confirm contract at all. Transcription just produces
the text that pipeline.handle_message() / extract.extract_message() already parse,
so this is "typed chat, with speech instead of a keyboard," not a new contract.
"""
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from . import stubs
from .errors import use_stubs

router = APIRouter()

# A voice note is a few seconds to a couple minutes of compressed speech -- generous
# but far below a bill photo's 15 MB cap.
MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/api/voice")
async def voice(
    shop_id: int = Form(...),
    sender: str = Form(...),
    audio: UploadFile = File(...),
) -> dict[str, Any]:
    raw = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(413, f"audio over {MAX_AUDIO_BYTES // 1024 // 1024} MB")
    if not raw:
        raise HTTPException(400, "empty audio")

    from .. import voice as voice_module
    try:
        transcript = await run_in_threadpool(voice_module.transcribe, raw)
    except voice_module.VoiceError as e:
        raise HTTPException(400, str(e))

    if use_stubs():
        return {
            "transcript": transcript["text"],
            "detected_lang": transcript["lang"],
            **stubs.chat(),
        }

    from .. import pipeline
    try:
        result = await run_in_threadpool(pipeline.handle_message, shop_id, sender, transcript["text"])
    except pipeline.BadRequestError as e:
        raise HTTPException(400, str(e))

    return {"transcript": transcript["text"], "detected_lang": transcript["lang"], **result}
