"""Alias / fuzzy / near-tie / learn. Needs no model -- fully testable with fixtures.

The near-tie rule is the one piece of logic the whole project is built around: `amul`
scores ~90 against both Amul Butter and Amul Milk, and taking the top match is right
half the time and silently wrong the rest. So a near-tie is ALWAYS ambiguous,
regardless of how high the top score is.
"""
from __future__ import annotations

from rapidfuzz import fuzz

from . import db

# Below this, nothing is "close" -- unknown, offer to create.
UNKNOWN_THRESHOLD = 60
# At or above this, with no near-tie, the top match is confident enough to pre-tick.
FUZZY_THRESHOLD = 80
# Top two within this many points of each other -> ambiguous, no matter how high.
NEAR_TIE_MARGIN = 5
MAX_CANDIDATES = 3


def resolve(shop_id: int, name: str) -> dict:
    """
    Returns:
        {"status": "exact" | "fuzzy" | "ambiguous" | "unknown",
         "sku_id": int | None,
         "candidates": [{"sku_id": int, "name": str, "score": int}]}

    In order:
      1. Exact alias hit, or the name matches a SKU's own name exactly -> "exact"
      2. Top fuzzy score >= FUZZY_THRESHOLD and clearly ahead of the second -> "fuzzy"
      3. Near-tie (top two within NEAR_TIE_MARGIN) -> "ambiguous", regardless of score
      4. Nothing close -> "unknown"
    """
    name = (name or "").strip().lower()
    if not name:
        return _result("unknown")

    alias = db.get_alias(shop_id, name)
    if alias is not None:
        return _result("exact", sku_id=alias["sku_id"])

    skus = db.list_skus(shop_id)
    for sku in skus:
        if sku["name"].strip().lower() == name:
            return _result("exact", sku_id=sku["id"])

    if not skus:
        return _result("unknown")

    aliases = db.list_aliases(shop_id)
    candidates = _score_candidates(name, skus, aliases)

    top = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    if top["score"] < UNKNOWN_THRESHOLD:
        return _result("unknown")

    # Checked before the plain fuzzy-threshold branch deliberately: a near-tie
    # overrides even a very high top score (see module docstring).
    if second is not None and (top["score"] - second["score"]) <= NEAR_TIE_MARGIN:
        # Only show candidates genuinely competing with the top score, not whatever
        # happened to be 3rd by raw rank -- real-model testing surfaced "aata" coming
        # back ambiguous against Aashirvaad Atta (75) and Tata Salt (73, the actual
        # near-tie partner) *and* Patanjali Ghee (68), which isn't part of the tie at
        # all and just adds a confusing third option to the dropdown.
        relevant = [c for c in candidates if c["score"] >= top["score"] - NEAR_TIE_MARGIN]
        return _result("ambiguous", candidates=relevant[:MAX_CANDIDATES])

    if top["score"] >= FUZZY_THRESHOLD:
        return _result("fuzzy", sku_id=top["sku_id"])

    # Close-ish (between UNKNOWN_THRESHOLD and FUZZY_THRESHOLD) but not a near-tie and
    # not confident enough to pre-tick -- this used to come back "ambiguous" with
    # candidates, on the theory that showing options beats silently filing it under
    # "unknown". Real-model testing against tests/bills/kannada-01.jpg proved that
    # wrong: a genuinely uncatalogued item ("pav bhaji", not one of the 30 seeded
    # SKUs) scored 60 against "Red Label Tea" with nothing else close, and came back
    # a nonsense "ambiguous" dropdown instead of "unknown" + create-new. The frozen
    # four-state contract (IMPLEMENTATION.md) doesn't have a fifth "maybe" state
    # either -- outside a near-tie, nothing-close is exactly what "unknown" means.
    return _result("unknown")


def learn_alias(shop_id: int, text: str, sku_id: int) -> None:
    """Called only from the confirm step, when a human actually picked the SKU. A
    fuzzy auto-accept must never reach this -- nobody confirmed it, and cementing an
    unconfirmed guess is how one slightly-off match becomes permanently wrong.
    """
    text = (text or "").strip().lower()
    if not text:
        return
    db.upsert_alias(shop_id, text, sku_id)


def _score_candidates(name: str, skus: list[dict], aliases: list[dict]) -> list[dict]:
    scored: dict[int, dict] = {}
    for sku in skus:
        score = round(fuzz.WRatio(name, sku["name"].lower()))
        scored[sku["id"]] = {"sku_id": sku["id"], "name": sku["name"], "score": score}

    sku_names = {sku["id"]: sku["name"] for sku in skus}
    for alias in aliases:
        score = round(fuzz.WRatio(name, alias["text"]))
        existing = scored.get(alias["sku_id"])
        if existing is None or score > existing["score"]:
            scored[alias["sku_id"]] = {
                "sku_id": alias["sku_id"],
                "name": sku_names.get(alias["sku_id"], alias["text"]),
                "score": score,
            }

    return sorted(scored.values(), key=lambda c: c["score"], reverse=True)


def _result(status: str, sku_id: int | None = None, candidates: list[dict] | None = None) -> dict:
    return {"status": status, "sku_id": sku_id, "candidates": candidates or []}
