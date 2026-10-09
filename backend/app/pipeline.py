"""scan + confirm orchestration -- the only module that imports across the other
owners' boundaries (db, units, resolver, inventory, reply are Lokesh's; routes that
call into this are Saket's). See IMPLEMENTATION.md for the full module contracts.

Steps 1-5 below (scan_bill) are read-only, per the architecture in README/IMPLEMENTATION.
confirm_scan is the only function in the whole project that writes to the ledger.
"""
from __future__ import annotations

import json
import time

from . import db, extract, imageprep, inventory, ocr, reorder, reply, resolver, units

# Single hardcoded demo shop for now (see README "Known limitations" -- no
# multi-tenancy yet), so there's no per-shop language preference to read. Hindi
# matches the demo's example replies in docs/api-contract.md.
DEFAULT_LANG = "hi"


def _require_shop(shop_id: int) -> None:
    if db.get_shop(shop_id) is None:
        raise BadRequestError(f"unknown shop {shop_id}")


def scan_bill(shop_id: int, image: bytes, direction: str = "stock_in") -> dict:
    """Photo in, review payload out. Writes nothing to the ledger.

    1. imageprep.prepare()
    2. ocr.read_bill() -- illegible short-circuits here, before extraction
    3. extract.extract_line() per line
    4. units.normalize_unit() per item -- unknown unit flags the row, isn't an error
    5. resolver.resolve() per item -- attaches match status + candidates
    6. Persist to `scans` with status "pending" and the given `direction`, return
       the review payload

    `direction` is "stock_in" (a supplier bill -- the original, still the default)
    or "stock_out" (a sales bill/invoice the shopkeeper is photographing to book a
    sale in bulk, instead of typing it line by line into /api/chat). It only
    changes which way confirm_scan moves the ledger -- extraction and resolution
    don't care which direction a line is going. Stored on the scan itself rather
    than trusted from the confirm call, so a client can't change which way a bill
    books after the fact.
    """
    if direction not in ("stock_in", "stock_out"):
        raise BadRequestError(f"unknown direction {direction!r}")
    _require_shop(shop_id)
    total_start = time.perf_counter()

    prepared = imageprep.prepare(image)

    ocr_start = time.perf_counter()
    bill = ocr.read_bill(prepared)
    ocr_ms = round((time.perf_counter() - ocr_start) * 1000)

    lang = DEFAULT_LANG

    if not bill["legible"]:
        return {
            "scan_id": None,
            "legible": False,
            "confidence": bill["confidence"],
            "script": bill["script"],
            "raw_text": bill["raw_text"],
            "reply": reply.illegible(lang),
            "lang": lang,
            "direction": direction,
            "items": [],
            "warnings": [],
            "debug": {
                "extract_source": None,
                "ocr_ms": ocr_ms,
                "total_ms": round((time.perf_counter() - total_start) * 1000),
            },
        }

    items: list[dict] = []
    warnings: list[str] = []
    extract_sources: set[str] = set()

    for idx, line in enumerate(bill["lines"]):
        parsed = extract.extract_line(line)
        extract_sources.add(parsed["_source"])

        unit = units.normalize_unit(parsed.get("unit") or "", lang="en")
        unit_ok = unit is not None
        if not unit_ok:
            warnings.append(f'line {idx + 1}: unit "{parsed.get("unit")}" not recognised')

        resolution = resolver.resolve(shop_id, parsed["name"])
        resolved_sku = db.get_sku(resolution["sku_id"]) if resolution["sku_id"] else None

        items.append({
            "line_index": idx,
            "line": line,
            "name": parsed["name"],
            "qty": parsed["qty"],
            "unit": unit or parsed.get("unit"),
            "unit_ok": unit_ok,
            "price_paise": parsed.get("price_paise"),
            "resolution": {
                "status": resolution["status"],
                "sku_id": resolution["sku_id"],
                "sku_name": resolved_sku["name"] if resolved_sku else None,
                "candidates": resolution["candidates"],
            },
        })

    scan_id = db.create_scan(
        shop_id=shop_id,
        raw_text=bill["raw_text"],
        items_json=json.dumps(items),
        status="pending",
        direction=direction,
    )

    # A line only counts as a silent fallback if nothing on the bill used the model --
    # a single failed line falling back to rules.py while the rest used the LLM is
    # still worth surfacing honestly rather than collapsed into one bit.
    extract_source = "rule" if extract_sources == {"rule"} else "llm"

    return {
        "scan_id": scan_id,
        "legible": True,
        "confidence": bill["confidence"],
        "script": bill["script"],
        "raw_text": bill["raw_text"],
        "reply": reply.scan_summary(items, lang, direction=direction),
        "lang": lang,
        "direction": direction,
        "items": items,
        "warnings": warnings,
        "debug": {
            "extract_source": extract_source,
            "ocr_ms": ocr_ms,
            "total_ms": round((time.perf_counter() - total_start) * 1000),
        },
    }


def confirm_scan(shop_id: int, scan_id: int, decisions: list[dict]) -> dict:
    """The only function in the project that writes to the ledger.

    1. Load the pending scan; reject (409, raised as ValueError here and translated
       by the route) if it's already confirmed -- a double-tap on Confirm must not
       book the bill twice.
    2. For each decision: "book" -> apply against sku_id; "skip" -> ignore;
       "new" -> create_sku() then apply.
    3. Where the shopkeeper picked a SKU for an unresolved line -> resolver.learn_alias().
       Never called for a plain "book" against an already-exact match -- nothing was
       actually decided there.
    4. inventory.apply_scan() in one transaction.
    5. Mark the scan "confirmed", return the actions.
    """
    _require_shop(shop_id)

    if not isinstance(decisions, list) or not decisions:
        raise BadRequestError("decisions must be a non-empty list")

    scan = db.get_scan(scan_id)
    if scan is None:
        raise BadRequestError(f"unknown scan {scan_id}")
    if scan["shop_id"] != shop_id:
        raise BadRequestError(f"scan {scan_id} does not belong to shop {shop_id}")
    if scan["status"] == "confirmed":
        raise ScanAlreadyConfirmedError(f"scan {scan_id} already confirmed")

    original_items = {item["line_index"]: item for item in json.loads(scan["items_json"])}

    confirmed_items = []
    aliases_learned = []
    skipped = 0

    for decision in decisions:
        action = decision.get("action")
        line_index = decision.get("line_index")
        if line_index is None or line_index not in original_items:
            raise BadRequestError(f"decision references unknown line_index {line_index!r}")
        original = original_items[line_index]

        if action == "skip":
            skipped += 1
            continue

        if action == "new":
            name = decision.get("name")
            if not name:
                raise ValidationError(f"line {line_index}: \"new\" requires a name")
            sku_id = inventory.create_sku(shop_id, name, decision.get("unit"))
        elif action == "book":
            sku_id = decision.get("sku_id")
            if not sku_id:
                raise ValidationError(f"line {line_index}: \"book\" requires a sku_id")
        else:
            raise BadRequestError(f"line {line_index}: unknown action \"{action}\"")

        # Only a line the resolver couldn't already place on its own counts as a
        # taught alias -- learn_alias must never fire for an already-"exact" match
        # that the shopkeeper simply left alone (see resolver.py's contract: a fuzzy
        # auto-accept must never write an alias either, since nobody confirmed it).
        original_status = original.get("resolution", {}).get("status")
        if original_status in ("ambiguous", "unknown") and original.get("name"):
            aliases_learned.append({"text": original["name"], "sku_id": sku_id})
            resolver.learn_alias(shop_id, original["name"], sku_id)

        confirmed_items.append({
            "line_index": line_index,
            "sku_id": sku_id,
            "qty": decision.get("qty", original.get("qty")),
            "unit": decision.get("unit", original.get("unit")),
            "price_paise": decision.get("price_paise", original.get("price_paise")),
        })

    # Direction comes from the scan itself, not the confirm call -- it was fixed at
    # scan time (see scan_bill's docstring) so a client can't flip which way a bill
    # books after the fact.
    direction = scan["direction"]
    actions = inventory.apply_scan(shop_id, scan_id, confirmed_items, direction=direction)
    db.set_scan_status(scan_id, "confirmed")

    return {
        "reply": reply.confirm_summary(actions, DEFAULT_LANG, direction=direction),
        "lang": DEFAULT_LANG,
        "actions": actions,
        "aliases_learned": aliases_learned,
        "skipped": skipped,
    }


def handle_message(shop_id: int, sender: str, text: str) -> dict:
    """A typed sentence -> a reply, and a stock write only for a real stock_in /
    stock_out intent. A "query" intent never reaches the resolver for a write --
    it's a read-only lookup (see docs/api-contract.md, `hi-3` test case: "2 kg aata
    chahiye" parses as a clean item but is a request, not a delivery).
    """
    _require_shop(shop_id)
    parsed = extract.extract_message(text)
    intent = parsed["intent"]
    lang = parsed["lang"]

    if intent == "query":
        # Read-only lookup path: no items are written regardless of what extraction
        # found, by construction -- query never reaches apply_movement.
        rows = []
        for item in parsed["items"]:
            resolution = resolver.resolve(shop_id, item["name"])
            if resolution["status"] not in ("exact", "fuzzy"):
                continue
            sku = db.get_sku(resolution["sku_id"])
            if sku is None:
                continue
            rows.append({
                "name": sku["name"],
                "qty": sku["current_qty"],
                "unit": sku["canonical_unit"],
                "days_of_cover": reorder.days_of_cover(sku["id"]),
            })

        return {
            "reply": reply.stock_query_answer(rows, lang),
            "lang": lang,
            "actions": [],
            "debug": {"extract_source": parsed["_source"], "detected_lang": lang},
        }

    direction = "stock_in" if intent == "stock_in" else "stock_out"
    actions = []
    for item in parsed["items"]:
        resolution = resolver.resolve(shop_id, item["name"])
        if resolution["status"] not in ("exact", "fuzzy"):
            # An ambiguous or unknown item from a typed message has nowhere to go
            # without a human picking one -- same principle as the scan path, just
            # with no review table to defer to here. Surface it, don't guess.
            continue

        sku_id = resolution["sku_id"]
        unit = units.normalize_unit(item.get("unit") or "", lang=lang) or item.get("unit")
        qty_canonical, _confident = units.convert(item["qty"], unit, sku_id) if unit else (item["qty"], False)

        inventory.apply_movement(
            shop_id, sku_id, direction, qty_canonical,
            price_paise=item.get("price_paise"), unit_as_said=item.get("unit"),
        )
        actions.append({"sku_id": sku_id, "direction": direction, "qty": qty_canonical, "unit": unit})

    # No resolved action means every item in the message was ambiguous, unknown, or
    # unparseable -- reply.stock_query_answer's empty-rows case ("couldn't find that
    # item") reads naturally here too, since the shopkeeper needs the same nudge to
    # re-check the name.
    return {
        "reply": reply.confirm_summary(actions, lang) if actions else reply.stock_query_answer([], lang),
        "lang": lang,
        "actions": actions,
        "debug": {"extract_source": parsed["_source"], "detected_lang": lang},
    }


class PipelineError(Exception):
    """Base for the errors below. A route can catch this broadly for a generic 500
    fallback, or catch the specific subclasses to pick the right status code.
    """


class BadRequestError(PipelineError):
    """Maps to 400 per docs/api-contract.md: bad shop_id, unknown scan_id, a decision
    for a line_index the scan doesn't have, or an unrecognised action.
    """


class ValidationError(PipelineError):
    """Maps to 422 per docs/api-contract.md: a `book` decision with no sku_id, or a
    `new` with no name.
    """


class ScanAlreadyConfirmedError(PipelineError):
    """Maps to 409 per docs/api-contract.md. A double-tap on Confirm must not book the
    bill twice.
    """
