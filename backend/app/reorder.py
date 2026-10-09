"""Days of cover -- current stock divided by the recent average daily sell-through.

Needs the 14 days of seeded sales history to show anything meaningful; a SKU with no
stock_out movements in the window has no sell-through rate to divide by, so it reports
`None` rather than a misleading infinity or zero.
"""
from __future__ import annotations

import time

from . import db

WINDOW_DAYS = 14


def days_of_cover(sku_id: int, window_days: int = WINDOW_DAYS) -> float | None:
    sku = db.get_sku(sku_id)
    if sku is None:
        return None

    since_ts = time.time() - window_days * 86400
    total_out = db.sum_stock_out(sku_id, since_ts)
    if total_out <= 0:
        return None

    avg_daily = total_out / window_days
    if avg_daily <= 0:
        return None

    return round(sku["current_qty"] / avg_daily, 1)
