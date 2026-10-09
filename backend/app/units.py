"""Unit vocabulary (English, Hindi, Kannada, printed-bill abbreviations) and per-SKU
conversion. See tests/corpus.md for the vocabulary table this is built from and the
known collisions this must not reintroduce.
"""
from __future__ import annotations

import json

from . import db

UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"]

# Flat synonym map across languages -- item text reaching this module is already
# Latin-script per convention (OCR transliterates before anything else sees it), so a
# single lowercase lookup covers en/hi/kn without per-language branching. `lang` is
# kept as a parameter for forward compatibility (a future script-specific collision)
# but isn't needed to disambiguate anything in the current vocabulary.
_SYNONYMS: dict[str, list[str]] = {
    "packet": [
        "packet", "packets", "pkt", "pkts", "pack", "packs", "pudiya",
        "pyaket", "pyaket.",
    ],
    "box": [
        "box", "boxes", "case", "cases", "carton", "cartons", "ctn",
        "peti", "dabba", "pettige",
    ],
    "sack": [
        "sack", "sacks", "bag", "bags", "bdl", "bundle", "bundles", "bori", "katta", "cheela",
        # "moote" is the universal Kannada kirana-trade word for a sack of grain/flour/sugar --
        # verified correction from tests/corpus.md, more common in the trade than "cheela".
        "moote",
    ],
    "dozen": ["dozen", "dzn", "doz", "darzan", "dajan"],
    "kg": ["kg", "kgs", "kilo", "kilos", "kilogram", "kilograms", "keji"],
    # Deliberately excludes bare "g" -- it would eat "parle g" (-> "parle"). Only
    # explicit gram spellings count.
    "gram": ["gram", "grams", "gm", "gms"],
    "litre": ["litre", "litres", "liter", "liters", "l", "ltr", "lt", "leetar"],
    "piece": [
        "piece", "pieces", "pc", "pcs", "nos", "no", "nag", "nags", "tundu",
        # "nang"/"nangu" are what Kannada shopkeepers actually say for a unit count --
        # far more common than "tundu" (which means a broken fragment/slice). "pees" is
        # the Kannada-ized loanword for "piece". Verified correction from tests/corpus.md.
        "nang", "nangu", "pees",
    ],
    # "pav" (quarter-kg) is a real printed-bill unit but isn't one of the eight
    # canonical units the API contract freezes (docs/api-contract.md). Leaving it
    # unmapped means normalize_unit("pav") -> None, which flags the row for the
    # shopkeeper to pick a unit rather than silently folding it into "kg" -- the
    # known collision this vocabulary must not reintroduce (see tests/corpus.md).
}

_LOOKUP: dict[str, str] = {
    syn.lower(): canonical for canonical, synonyms in _SYNONYMS.items() for syn in synonyms
}
# Canonical names map to themselves too (a value already normalized stays normalized).
_LOOKUP.update({unit: unit for unit in UNITS})

# Ratios that hold regardless of packaging -- a dozen is always 12 of something, 1 kg
# is always 1000 g. Packaging-dependent units (packet/box/sack) have NO generic entry:
# a box of Coke is 24, a box of something else isn't, so those can only convert
# confidently via a SKU's own `unit_conversions`.
_GENERIC_RATIOS: dict[tuple[str, str], float] = {
    ("dozen", "piece"): 12,
    ("piece", "dozen"): 1 / 12,
    ("kg", "gram"): 1000,
    ("gram", "kg"): 1 / 1000,
}


def normalize_unit(word: str, lang: str = "en") -> str | None:
    """Returns the canonical unit, or None for anything unrecognised.

    Never pass an unrecognised word through -- it would get stored as a SKU's
    canonical unit forever the first time someone picks "create new item" on it.
    """
    if not word:
        return None
    return _LOOKUP.get(word.strip().lower())


def convert(qty: float, from_unit: str, sku_id: int) -> tuple[float, bool]:
    """Returns (qty_in_canonical_unit, confident).

    `confident` is False when the conversion had to guess (no SKU-specific ratio and
    no universal one either) -- the caller gets the raw qty back unconverted rather
    than a silently wrong multiplier, and should treat that as worth flagging rather
    than booking blind.
    """
    sku = db.get_sku(sku_id)
    if sku is None:
        return qty, False

    canonical = sku["canonical_unit"]
    if from_unit == canonical:
        return qty, True

    try:
        sku_ratios = json.loads(sku.get("unit_conversions") or "{}")
    except (TypeError, ValueError):
        sku_ratios = {}

    if from_unit in sku_ratios:
        return qty * sku_ratios[from_unit], True

    generic = _GENERIC_RATIOS.get((from_unit, canonical))
    if generic is not None:
        return qty * generic, True

    return qty, False
