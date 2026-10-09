"""POST /api/scan (read-only) and POST /api/scan/confirm (the only writer)."""
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from .. import config
from . import stubs
from .errors import use_stubs

router = APIRouter()
log = config.get_logger("munim.scan")


class Decision(BaseModel):
    line_index: int
    action: str  # book | skip | new
    sku_id: int | None = None
    name: str | None = None
    qty: float | None = None
    unit: str | None = None
    price_paise: int | None = None


class ConfirmBody(BaseModel):
    shop_id: int
    scan_id: int
    decisions: list[Decision]


@router.post("/api/scan")
async def scan(shop_id: int = Form(...), sender: str = Form(...), image: UploadFile = File(...),
               direction: str = Form("stock_in"), fail: int = Query(0)) -> dict[str, Any]:
    raw = await image.read(config.MAX_UPLOAD_BYTES + 1)
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"image over {config.MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    if not raw:
        raise HTTPException(400, "empty image")
    if direction not in ("stock_in", "stock_out"):
        raise HTTPException(400, f"unknown direction {direction!r}")
    if use_stubs():
        return stubs.scan(fail=bool(fail))
    from .. import pipeline
    try:
        return await run_in_threadpool(pipeline.scan_bill, shop_id, raw, direction)
    except pipeline.BadRequestError as e:  # bad shop_id
        raise HTTPException(400, str(e))
    except ValueError as e:  # undecodable image from imageprep.prepare
        raise HTTPException(400, str(e))


@router.post("/api/scan/confirm")
async def confirm(body: ConfirmBody) -> dict[str, Any]:
    for d in body.decisions:
        if d.action not in ("book", "skip", "new"):
            raise HTTPException(400, f"unknown action {d.action!r} on line {d.line_index}")
        if d.action == "book" and d.sku_id is None:
            raise HTTPException(422, f"line {d.line_index}: book needs sku_id")
        if d.action == "new" and not d.name:
            raise HTTPException(422, f"line {d.line_index}: new needs name")
    if use_stubs():
        return stubs.confirm()
    from .. import pipeline
    decisions = [d.model_dump() for d in body.decisions]
    try:
        return await run_in_threadpool(pipeline.confirm_scan, body.shop_id, body.scan_id, decisions)
    except pipeline.ScanAlreadyConfirmedError as e:
        raise HTTPException(409, str(e))
    except pipeline.ValidationError as e:
        raise HTTPException(422, str(e))
    except pipeline.BadRequestError as e:
        raise HTTPException(400, str(e))
    except (KeyError, LookupError) as e:
        raise HTTPException(400, str(e))
