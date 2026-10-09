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


def apply_movement(shop_id: int, sku_id: int, direction: str, qty_canonical: float,
                    price_paise: int | None = None, unit_as_said: str | None = None,
                    scan_id: int | None = None, conn=None) -> None:
    """Records one ledger row and updates the SKU's running quantity (and cost/sell
    price, if a price was given). `current_qty` floors at 0; the ledger still records
    the full reported movement, so the audit trail never lies even when the number on
    screen does.
    """
    owns_conn = conn is None
    conn = conn or db.get_connection()
    try:
        sku = db.get_sku(sku_id, conn=conn)
        if sku is None:
            raise ValueError(f"unknown sku {sku_id}")
        if direction not in ("stock_in", "stock_out"):
            raise ValueError(f"unknown direction {direction!r}")

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
            updates["current_qty"] = max(0, sku["current_qty"] - qty_canonical)
            if price_paise is not None:
                updates["sell_price"] = price_paise

        db.update_sku(sku_id, conn=conn, **updates)

        if owns_conn:
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def apply_scan(shop_id: int, scan_id: int, confirmed_items: list[dict]) -> list[dict]:
    """One transaction for the whole bill -- all-or-nothing. A supplier bill is
    always `stock_in` (README: "A supplier bill is always stock_in").

    Each item in `confirmed_items` is
        {"line_index", "sku_id", "qty", "unit", "price_paise"}
    (as built by pipeline.confirm_scan from the shopkeeper's decisions, trusting the
    confirmed values over whatever was originally parsed).
    """
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
                shop_id, sku_id, "stock_in", qty_canonical,
                price_paise=canonical_price, unit_as_said=stated_unit,
                scan_id=scan_id, conn=conn,
            )

            updated = db.get_sku(sku_id, conn=conn)
            actions.append({
                "sku_id": sku_id,
                "sku_name": sku["name"],
                "direction": "stock_in",
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
