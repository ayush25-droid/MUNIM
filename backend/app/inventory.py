"""Movements, SKU creation, stock levels.

Price convention used throughout this file: `price_paise` on a confirmed item is the
price per the STATED unit (e.g. per dozen, per box) as written on the bill -- exactly
what the shopkeeper would read off it. When `units.convert` changes that unit to the
SKU's canonical one, the price is divided by the same ratio used for the quantity
("Stated price converts by the same ratio as the quantity" -- IMPLEMENTATION.md), so a
rate per dozen lands as a correct per-piece cost rather than a 12x-inflated one.
"""
from __future__ import annotations

from . import db, reorder, units

LOW_STOCK_DAYS = 3
# Tolerance for float rounding from unit conversion ratios (e.g. box -> litre) --
# without it, a sale of exactly the remaining stock could spuriously fail by a
# fraction of a unit.
_EPSILON = 1e-6


class InsufficientStockError(ValueError):
    """Raised when a stock_out would take a SKU below zero. A sale that can't
    actually be fulfilled must not look like it succeeded -- silently flooring
    `current_qty` at 0 (the old behaviour) hid a real problem: the shopkeeper would
    see "sale booked" and a wrong, lower stock number instead of being told the
    sale can't happen as stated. Raised before any write, so a blocked sale leaves
    no trace -- no ledger row, no quantity change.
    """

    def __init__(self, sku_name: str, have: float, need: float, unit: str):
        self.sku_name = sku_name
        self.have = have
        self.need = need
        self.unit = unit
        super().__init__(f"insufficient stock for {sku_name}: have {have} {unit}, need {need} {unit}")


def apply_movement(shop_id: int, sku_id: int, direction: str, qty_canonical: float,
                    price_paise: int | None = None, unit_as_said: str | None = None,
                    scan_id: int | None = None, conn=None) -> None:
    """Records one ledger row and updates the SKU's running quantity (and cost/sell
    price, if a price was given). Raises `InsufficientStockError` instead of
    writing anything if a stock_out would take `current_qty` negative -- see that
    class's docstring.
    """
    owns_conn = conn is None
    conn = conn or db.get_connection()
    try:
        sku = db.get_sku(sku_id, conn=conn)
        if sku is None:
            raise ValueError(f"unknown sku {sku_id}")
        if direction not in ("stock_in", "stock_out"):
            raise ValueError(f"unknown direction {direction!r}")
        if direction == "stock_out" and qty_canonical > sku["current_qty"] + _EPSILON:
            raise InsufficientStockError(
                sku["name"], sku["current_qty"], qty_canonical, sku["canonical_unit"],
            )

        db.insert_ledger(
            sku_id, direction, qty_canonical,
            unit_as_said=unit_as_said, price_paise=price_paise, scan_id=scan_id, conn=conn,
        )

        updates: dict = {}
        if direction == "stock_in":
            updates["current_qty"] = sku["current_qty"] + qty_canonical
            if price_paise is not None:
                updates["cost_per_unit"] = price_paise
        else:
            # The insufficient-stock check above already guarantees this can't go
            # negative; max(0, ...) stays only as a defensive floor against float
            # rounding at the boundary, not as the primary behaviour anymore.
            updates["current_qty"] = max(0, sku["current_qty"] - qty_canonical)
            if price_paise is not None:
                updates["sell_price"] = price_paise

        db.update_sku(sku_id, conn=conn, **updates)

        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def apply_scan(shop_id: int, scan_id: int, confirmed_items: list[dict],
                direction: str = "stock_in") -> list[dict]:
    """One transaction for the whole bill -- all-or-nothing. A supplier bill is
    `stock_in`; a sales bill/invoice photographed to book a sale in bulk (instead of
    typing it line by line into /api/chat) is `stock_out` -- `direction` comes from
    the scan itself (pipeline.confirm_scan reads it off the stored scan row, not the
    confirm call), so it can't be a lie: whatever the shopkeeper picked before
    photographing the bill is what actually books.

    Each item in `confirmed_items` is
        {"line_index", "sku_id", "qty", "unit", "price_paise"}
    (as built by pipeline.confirm_scan from the shopkeeper's decisions, trusting the
    confirmed values over whatever was originally parsed).
    """
    if direction not in ("stock_in", "stock_out"):
        raise ValueError(f"unknown direction {direction!r}")
    conn = db.get_connection()
    actions: list[dict] = []
    try:
        for item in confirmed_items:
            sku_id = item["sku_id"]
            sku = db.get_sku(sku_id, conn=conn)
            if sku is None:
                raise ValueError(f"unknown sku {sku_id}")

            stated_qty = item.get("qty") or 0
            stated_unit = item.get("unit") or sku["canonical_unit"]
            qty_canonical, _confident = units.convert(stated_qty, stated_unit, sku_id)

            price_paise = item.get("price_paise")
            canonical_price = price_paise
            if price_paise is not None and stated_qty and qty_canonical:
                ratio = qty_canonical / stated_qty
                if ratio:
                    canonical_price = round(price_paise / ratio)

            apply_movement(
                shop_id, sku_id, direction, qty_canonical,
                price_paise=canonical_price, unit_as_said=stated_unit,
                scan_id=scan_id, conn=conn,
            )

            updated = db.get_sku(sku_id, conn=conn)
            actions.append({
                "sku_id": sku_id,
                "sku_name": sku["name"],
                "direction": direction,
                "qty": qty_canonical,
                "unit": sku["canonical_unit"],
                "new_qty": updated["current_qty"],
            })

        conn.commit()
        return actions
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_sku(shop_id: int, name: str, unit: str | None) -> int:
    """Validates `unit` against the canonical list, falling back to "packet" rather
    than storing an unrecognised unit as a SKU's canonical unit forever.
    """
    canonical_unit = unit if unit in units.UNITS else "packet"
    return db.create_sku(shop_id, name, canonical_unit)


def levels(shop_id: int) -> list[dict]:
    rows = []
    for sku in db.list_skus(shop_id):
        cover = reorder.days_of_cover(sku["id"])
        rows.append({
            "sku_id": sku["id"],
            "name": sku["name"],
            "qty": sku["current_qty"],
            "unit": sku["canonical_unit"],
            "cost_per_unit": sku["cost_per_unit"],
            "days_of_cover": cover,
            "low": cover is not None and cover <= LOW_STOCK_DAYS,
        })
    return rows
