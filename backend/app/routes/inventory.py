"""GET /api/inventory"""
from typing import Any

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from . import stubs
from .errors import use_stubs

router = APIRouter()


@router.get("/api/inventory")
async def get_inventory(shop_id: int = 1) -> dict[str, Any]:
    if use_stubs():
        return stubs.inventory()
    from .. import inventory, reorder
    levels = await run_in_threadpool(inventory.levels, shop_id)
    return {"items": levels}
