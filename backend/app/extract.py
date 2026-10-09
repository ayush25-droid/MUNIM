"""Text line / typed message -> structured item, via the model, with unit constrained
by enum. Falls through to rules.py on any failure -- this module never raises to its
caller, so a bad model response degrades to a flagged row instead of a crashed scan.

The unit enum is the single most important part of the schema: without it the model
invents units like "units" or "box of 10", and every downstream step (resolver,
inventory, units.convert) degrades silently from there.
"""
from __future__ import annotations

from . import llm, rules

try:
    from .units import UNITS  # Lokesh's canonical unit list, once it exists.
except ImportError:  # pragma: no cover - units.py not built yet.
    UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"]

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "qty": {"type": "number"},
        "unit": {"type": "string", "enum": UNITS},
        "price_paise": {"type": "integer"},
    },
    "required": ["name", "qty", "unit"],
}

LINE_PROMPT_TEMPLATE = """Extract one item from this single bill line:

"{line}"

A bill line has this shape: <qty> <unit word> <product name, maybe with its own size/weight> <price>.
Extract the unit word into "unit" FIRST -- it's always the word immediately after the
quantity (e.g. "bori" in "5 bori aata", "pc" in "5 pc Amul Butter 500g"). Whatever number
or weight appears AFTER the product name (like "500g" in "Amul Butter 500g") is part of
the product's own name, not a second unit -- never let it replace or merge with "unit".

Return a JSON object:
- "name": the item name, in LATIN SCRIPT, lowercase, with the leading quantity and unit
  word removed. If the line already gives a transliterated name, keep it as-is -- don't
  translate the meaning, just lowercase it. KEEP a size/weight ONLY when it is fused
  directly onto a word with no space, right after the product name, with its own unit
  suffix attached (e.g. "500g", "1L", "250ml" in "Amul Butter 500g") -- that's what tells
  two sizes of the same product apart, so dropping it is how "Amul Butter 500g" gets
  silently matched to "Amul Butter 100g". A bare number with nothing attached to it (no
  "g"/"ml"/"l"/"kg" suffix) is NEVER part of the name -- it is either the leading
  quantity (already removed) or the trailing price (goes in "price_paise", never in
  "name"). Examples: "5 bori aata 4600" -> unit "sack", name "aata" (no size suffix
  anywhere, "4600" is just the price). "1 ctn amul milk 720" -> unit "box", name "amul
  milk" (no size suffix, "720" is just the price). "5 pc Amul Butter 500g 270.00" -> unit
  "piece", name "amul butter 500g" (500g has the "g" suffix fused on, so it stays).
- "qty": the quantity, as a number.
- "unit": the unit of measure. It MUST be exactly one of: {units}. Pick the closest
  match for the unit word right after the quantity (e.g. "pkt"/"pack" -> "packet", "dzn"
  -> "dozen", "nos"/"pc" -> "piece", "bori" -> "sack"). If no unit is stated at all, use
  "piece".
- "price_paise": the price as an integer number of paise (rupees * 100). If the line
  gives rupees, multiply by 100. If no price is stated, use 0.

Return only the JSON object."""

MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["query", "stock_in", "stock_out"]},
        "lang": {"type": "string", "enum": ["en", "hi", "kn"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "number"},
                    "unit": {"type": "string", "enum": UNITS},
                    "price_paise": {"type": "integer"},
                },
                "required": ["name", "qty", "unit"],
            },
        },
    },
    "required": ["intent", "lang", "items"],
}

MESSAGE_PROMPT_TEMPLATE = """A kirana (small grocery) shopkeeper, or a customer, sent
this message. It may be in English, Romanized Hindi, Romanized Kannada, or a mix:

"{text}"

Classify it and extract any items:

- "intent":
    - "query" -- asking about stock, a price, or anything else that doesn't change
      stock. This INCLUDES a request or need, e.g. "2 kg aata chahiye" (I need 2kg of
      flour) is a query, not a delivery -- nothing should be written to stock just
      because someone said they want or need something.
    - "stock_in" -- goods arriving / being received, e.g. "20 packets of parle-g came
      in" or "maal aaya".
    - "stock_out" -- an actual completed sale, e.g. "das maggi bik gaye" (10 Maggi got
      sold) or "sold 5 kg sugar". Requires an explicit sale verb -- a bare "hua"/"gaya"
      auxiliary is NOT enough on its own (e.g. "rate badh gaya" is a price change, not
      a sale).
  When in doubt between "query" and a stock-changing intent, prefer "query" -- a missed
  update can be re-sent, but a phantom stock write corrupts the books.
- "lang": the dominant language of the message -- "en", "hi", or "kn".
- "items": a list of items mentioned, each with "name" (Latin script, lowercase, keeping
  any size/weight/pack descriptor that's part of the product name -- e.g. "500g", "1l"),
  "qty", "unit" (exactly one of: {units}), and "price_paise" (integer paise, 0 if not
  stated). Empty list if intent is "query" and no concrete item/quantity is being
  reported, or if no item is mentioned at all.

Return only the JSON object."""


def extract_line(line: str) -> dict:
    """One bill line -> `{"name", "qty", "unit", "price_paise", "_source"}`.

    Tries the model first; on any failure (timeout, unreachable, malformed response)
    falls through to `rules.extract_line`. `_source` is "llm" or "rule" so a silent
    fallback is visible in the API response rather than buried in a log.
    """
    try:
        result = llm.generate(
            LINE_PROMPT_TEMPLATE.format(line=line, units=", ".join(UNITS)),
            schema=LINE_SCHEMA,
        )
        if not isinstance(result, dict):
            raise llm.LLMError("line extraction did not return an object")
        return {
            "name": str(result.get("name", "")).strip().lower(),
            "qty": result.get("qty", 0),
            "unit": result.get("unit") if result.get("unit") in UNITS else None,
            "price_paise": _as_optional_int(result.get("price_paise")),
            "_source": "llm",
        }
    except llm.LLMError:
        return rules.extract_line(line)


def extract_message(text: str) -> dict:
    """A typed sentence -> `{"intent", "lang", "items", "_source"}`.

    Same fallback discipline as `extract_line`: never raises, falls through to
    `rules.extract_message` on any model failure.
    """
    try:
        result = llm.generate(
            MESSAGE_PROMPT_TEMPLATE.format(text=text, units=", ".join(UNITS)),
            schema=MESSAGE_SCHEMA,
        )
        if not isinstance(result, dict):
            raise llm.LLMError("message extraction did not return an object")

        intent = result.get("intent")
        if intent not in ("query", "stock_in", "stock_out"):
            intent = "query"

        lang = result.get("lang")
        if lang not in ("en", "hi", "kn"):
            lang = "en"

        items = []
        for raw_item in result.get("items") or []:
            if not isinstance(raw_item, dict):
                continue
            unit = raw_item.get("unit")
            items.append({
                "name": str(raw_item.get("name", "")).strip().lower(),
                "qty": raw_item.get("qty", 0),
                "unit": unit if unit in UNITS else None,
                "price_paise": _as_optional_int(raw_item.get("price_paise")),
            })

        return {"intent": intent, "lang": lang, "items": items, "_source": "llm"}
    except llm.LLMError:
        return rules.extract_message(text)


def _as_optional_int(value) -> int | None:
    """0 and missing both mean "no price stated" -- a real bill line never prices an
    item at zero, so collapsing both to None avoids the ambiguity downstream.
    """
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed != 0 else None
