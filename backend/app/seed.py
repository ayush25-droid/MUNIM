"""Demo shop, ~30 real kirana SKUs, a starting alias list, and 14 days of sales
history. The history isn't optional -- days-of-cover and the low-stock alert show
nothing without it (reorder.py divides by the trailing sell-through rate).

Run with `python -m app.seed`, or `python -m app.seed --reset` to wipe first.

Deliberately leaves "amul" and "maggi" un-aliased on their own (only the full names
are pre-seeded) -- those are the near-tie demo: the first scan that says just "amul"
or "maggi" should come back `ambiguous`, and only resolve silently after a human picks
once.
"""
from __future__ import annotations

import argparse
import os
import random
import time

from . import db

DEMO_SHOP_ID_HINT = int(os.getenv("DEMO_SHOP_ID", "1"))
SHOP_NAME = "Sharma General Store"

HISTORY_DAYS = 14
RNG_SEED = 42  # reproducible demo data run to run

# (name, canonical_unit, starting_qty, cost_per_unit_paise, sell_price_paise,
#  unit_conversions, avg_daily_sales)
SKUS: list[tuple[str, str, float, int, int, dict, float]] = [
    ("Parle-G Biscuit", "packet", 40, 480, 600, {}, 6),
    ("Good Day Biscuit", "packet", 25, 900, 1100, {}, 3),
    # Low starting stock against its own sell-through on purpose -- this and Amul Milk
    # below are the demo's "before" low-stock rows (Saket found the seeded shop had
    # none, so the dashboard showed nothing red for the "before" screenshot).
    ("Maggi Noodles 70g", "packet", 5, 1200, 1400, {}, 4),
    ("Maggi Masala 100g", "piece", 10, 9500, 11000, {}, 0.5),
    ("Aashirvaad Atta", "kg", 60, 4200, 4800, {}, 5),
    ("Basmati Rice", "kg", 50, 8500, 9500, {}, 3),
    ("Toor Dal", "kg", 35, 11000, 12500, {}, 2),
    ("Sugar", "kg", 40, 4000, 4500, {}, 3),
    ("Tata Salt", "packet", 20, 2000, 2500, {}, 1.5),
    ("Fortune Sunflower Oil 1L", "litre", 25, 13000, 14500, {}, 2),
    ("Amul Butter 100g", "packet", 18, 5200, 6000, {}, 1.5),
    ("Amul Milk 500ml", "litre", 3, 2600, 3000, {}, 4),
    ("Red Label Tea 250g", "packet", 15, 9800, 11000, {}, 1),
    ("Surf Excel 1kg", "packet", 12, 14500, 16500, {}, 1),
    ("Colgate Toothpaste", "piece", 20, 4500, 5500, {}, 1.5),
    ("Lifebuoy Soap", "piece", 30, 2800, 3500, {}, 2),
    ("Local Soap Bar", "piece", 25, 1200, 1500, {}, 1),
    ("Britannia Bread", "piece", 10, 3500, 4000, {}, 3),
    ("Haldiram Namkeen 200g", "packet", 16, 6500, 7500, {}, 1.5),
    ("Dettol Handwash", "piece", 14, 7500, 8800, {}, 0.8),
    ("Vim Dishwash Bar", "piece", 20, 1000, 1300, {}, 1.5),
    ("Coca-Cola 200ml", "piece", 48, 1500, 2000, {"box": 24}, 5),
    ("Thums Up 200ml", "piece", 48, 1500, 2000, {"box": 24}, 4),
    ("Frooti 200ml", "piece", 48, 1200, 1600, {"box": 24}, 3),
    ("Lays Chips", "packet", 36, 1000, 1500, {"box": 12}, 4),
    ("Kurkure", "packet", 24, 1000, 1500, {"box": 12}, 3),
    ("Horlicks 500g", "piece", 10, 18000, 21000, {}, 0.5),
    ("Bournvita 500g", "piece", 8, 17500, 20500, {}, 0.4),
    ("Patanjali Ghee 1L", "piece", 12, 55000, 62000, {}, 0.6),
    ("Local Candle Pack", "piece", 15, 2000, 2800, {}, 0.7),
]

# Shorthand a bill or a shopkeeper would already use, pre-seeded so most lines resolve
# "exact" from day one. Bare "amul" / "maggi" are deliberately absent -- see docstring.
STARTING_ALIASES: dict[str, str] = {
    "parle g": "Parle-G Biscuit",
    "parle-g": "Parle-G Biscuit",
    "good day": "Good Day Biscuit",
    "maggi noodles": "Maggi Noodles 70g",
    "maggi masala": "Maggi Masala 100g",
    "atta": "Aashirvaad Atta",
    "aashirvaad atta": "Aashirvaad Atta",
    "rice": "Basmati Rice",
    "basmati": "Basmati Rice",
    "dal": "Toor Dal",
    "toor dal": "Toor Dal",
    "chini": "Sugar",
    "namak": "Tata Salt",
    "tata salt": "Tata Salt",
    "fortune oil": "Fortune Sunflower Oil 1L",
    "sunflower oil": "Fortune Sunflower Oil 1L",
    "amul butter": "Amul Butter 100g",
    "amul milk": "Amul Milk 500ml",
    "chai patti": "Red Label Tea 250g",
    "red label": "Red Label Tea 250g",
    "surf": "Surf Excel 1kg",
    "surf excel": "Surf Excel 1kg",
    "colgate": "Colgate Toothpaste",
    "lifebuoy": "Lifebuoy Soap",
    "bread": "Britannia Bread",
    "haldiram": "Haldiram Namkeen 200g",
    "dettol": "Dettol Handwash",
    "vim": "Vim Dishwash Bar",
    "coke": "Coca-Cola 200ml",
    "coca cola": "Coca-Cola 200ml",
    "thums up": "Thums Up 200ml",
    "frooti": "Frooti 200ml",
    "lays": "Lays Chips",
    "kurkure": "Kurkure",
    "horlicks": "Horlicks 500g",
    "bournvita": "Bournvita 500g",
    "ghee": "Patanjali Ghee 1L",
    "patanjali ghee": "Patanjali Ghee 1L",
}


def seed(reset: bool = False) -> int:
    if reset and os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)

    db.init_db()
    rng = random.Random(RNG_SEED)

    shop_id = db.create_shop(SHOP_NAME)
    if shop_id != DEMO_SHOP_ID_HINT:
        print(
            f"warning: new shop id is {shop_id}, but DEMO_SHOP_ID is set to "
            f"{DEMO_SHOP_ID_HINT} -- update your .env or reset a clean database."
        )

    name_to_id: dict[str, int] = {}
    ledger_rows: list[dict] = []
    now = time.time()

    for name, unit, qty, cost, sell, conversions, avg_daily in SKUS:
        sku_id = db.create_sku(
            shop_id, name, unit,
            current_qty=qty, cost_per_unit=cost, sell_price=sell,
            unit_conversions=conversions,
        )
        name_to_id[name] = sku_id

        # 14 days of plausible sell-through, each day's qty jittered around the
        # SKU's average so reorder.days_of_cover() has something real to divide by.
        for day in range(HISTORY_DAYS, 0, -1):
            if avg_daily <= 0:
                continue
            day_qty = max(0, rng.gauss(avg_daily, avg_daily * 0.4))
            if day_qty < 0.1:
                continue
            day_qty = round(day_qty, 2) if unit in ("kg", "litre", "gram") else round(day_qty)
            if day_qty <= 0:
                continue
            ts = now - day * 86400 + rng.uniform(0, 86400 * 0.8)
            ledger_rows.append({
                "sku_id": sku_id,
                "direction": "stock_out",
                "qty": day_qty,
                "unit_as_said": unit,
                "price_paise": sell,
                "ts": ts,
            })

    db.insert_ledger_batch(ledger_rows)

    skipped = []
    for text, sku_name in STARTING_ALIASES.items():
        sku_id = name_to_id.get(sku_name)
        if sku_id is None:
            skipped.append(sku_name)
            continue
        db.upsert_alias(shop_id, text, sku_id)

    if skipped:
        print(f"warning: aliases referenced unknown SKU names: {skipped}")

    print(f"seeded shop_id={shop_id}, {len(SKUS)} SKUs, "
          f"{len(ledger_rows)} history rows, {len(STARTING_ALIASES)} starting aliases")
    return shop_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="wipe the database before seeding")
    args = parser.parse_args()
    seed(reset=args.reset)


if __name__ == "__main__":
    main()
