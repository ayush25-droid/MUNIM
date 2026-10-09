"""POST /api/chat: typed text for queries and corrections."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import stubs
from .errors import use_stubs

router = APIRouter()


class ChatBody(BaseModel):
    shop_id: int
    sender: str
    text: str


@router.post("/api/chat")
async def chat(body: ChatBody) -> dict[str, Any]:
    if use_stubs():
        return stubs.chat()
    from .. import pipeline
    try:
        return await run_in_threadpool(pipeline.handle_message, body.shop_id, body.sender, body.text)
    except pipeline.BadRequestError as e:
        raise HTTPException(400, str(e))
