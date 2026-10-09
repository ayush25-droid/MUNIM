"""Regex/keyword fallback extractor. Wired as extract.py's except path -- when the
model call or schema parse fails, this is what keeps a scan from producing nothing.

English + Hindi (Romanized) vocabulary only. Kannada has no rule path here; that's a
disclosed limitation (see README "Known limitations") -- a Kannada line that reaches
this module produces a flagged, unresolved row rather than a silent wrong guess.

Handles a surprising share of printed bills for free: `<qty> <unit> <name> <price>` is
the common shape of a printed line item.
"""
from __future__ import annotations

import re

try:
    from .units import UNITS  # Lokesh's canonical unit list, once it exists.
except ImportError:  # pragma: no cover - units.py not built yet.
    UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"]

# English + printed-bill abbreviations, and Romanized Hindi. Deliberately does not
# include bare "g" (it would eat "parle g") -- only "gm"/"gms"/"gram"/"grams" count.
UNIT_SYNONYMS: dict[str, list[str]] = {
    "packet": ["packet", "packets", "pkt", "pkts", "pack", "packs", "pudiya"],
    "box": ["box", "boxes", "case", "cases", "carton", "cartons", "ctn", "peti", "dabba"],
    "sack": ["sack", "sacks", "bag", "bags", "bdl", "bundle", "bundles", "bori", "katta"],
    "dozen": ["dozen", "dzn", "doz", "darzan"],
    "kg": ["kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"],
    "gram": ["gram", "grams", "gm", "gms"],
    "litre": ["litre", "litres", "liter", "liters", "l", "ltr", "lt"],
    "piece": ["piece", "pieces", "pc", "pcs", "nos", "no", "nag", "nags"],
}

_UNIT_LOOKUP: dict[str, str] = {
    syn.lower(): canonical
    for canonical, synonyms in UNIT_SYNONYMS.items()
    for syn in synonyms
    if canonical in UNITS
}

# <qty> <unit?> <name> <price?> -- unit and price are both optional so a line that's
# just "<qty> <name>" or has no trailing price still parses into something usable.
_LINE_RE = re.compile(
    r"""^\s*
        (?P<qty>\d+(?:\.\d+)?)
        \s*[.:]?\s*
        (?:(?P<unit>[a-zA-Z]+)\.?\s+)?
        (?P<rest>.+?)
        \s*$
    """,
    re.VERBOSE,
)

_TRAILING_PRICE_RE = re.compile(r"^(?P<name>.*\S)\s+(?P<price>\d+(?:\.\d+)?)\s*$")

# Romanized-Hindi / English keyword cues, used only by the rule-based message parser.
_QUERY_WORDS = {
    "kitna", "kitne", "kitni", "bacha", "bachi", "bache", "bacha hai", "left",
    "how", "chahiye", "chaiye", "need", "want", "available", "hai kya",
}
# Filler/cue words stripped out when guessing the item a query is about -- what's left
# over is taken as the item name (see extract_message's query branch below). Includes
# the query cues themselves plus common Hindi/English filler that isn't part of any
# item name.
_QUERY_FILLER_WORDS = _QUERY_WORDS | {
    "is", "are", "the", "a", "an", "of", "to", "stock", "hai", "hain", "kya",
    "mein", "ka", "ki", "ke", "many", "much",
}
_STOCK_OUT_WORDS = {
    "bik", "bika", "bike", "bikgaya", "bech", "becha", "bechi", "bechdiya",
    "nikla", "nikli", "sold", "sale",
}
_STOCK_IN_WORDS = {
    "aaya", "aaye", "aayi", "aagaya", "arrived", "arrive", "came", "mila", "mile",
    "mili", "receive", "received", "delivery", "delivered",
}

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_KANNADA_RE = re.compile(r"[ಀ-೿]")

# Romanized-Hindi-only cues (exclude English words that overlap in meaning, e.g.
# "need"/"left"/"sold") -- used to tell "kitna parle g bacha hai" apart from an
# English sentence that happens to share an intent keyword.
_HINDI_ROMAN_CUES = {
    "kitna", "kitne", "kitni", "bacha", "bachi", "bache", "hai", "bik", "bika",
    "bike", "bech", "becha", "bechi", "nikla", "nikli", "aaya", "aaye", "aayi",
    "aagaya", "mila", "mile", "mili", "chahiye", "chaiye", "gaya", "gaye", "gayi",
}


def _lookup_unit(token: str | None) -> str | None:
    if not token:
        return None
    return _UNIT_LOOKUP.get(token.lower())


def _split_name_price(text: str) -> tuple[str, int | None]:
    m = _TRAILING_PRICE_RE.match(text)
    if not m:
        return text.strip(), None
    try:
        price = float(m.group("price"))
    except ValueError:
        return text.strip(), None
    return m.group("name").strip(), round(price)


def extract_line(line: str) -> dict:
    """`<qty> <unit> <item name> <price>` -> structured item, via regex only.

    Returns {"name", "qty", "unit", "price_paise", "_source": "rule"}. Never raises --
    a line this can't parse comes back with qty=0 so the caller can flag the row rather
    than crash.
    """
    m = _LINE_RE.match(line)
    if not m:
        return {
            "name": line.strip().lower(),
            "qty": 0,
            "unit": None,
            "price_paise": None,
            "_source": "rule",
        }

    qty_raw = m.group("qty")
    unit_token = m.group("unit")
    rest = m.group("rest")

    unit = _lookup_unit(unit_token)
    if unit is None and unit_token:
        # Not a recognised unit word -- it's probably part of the item name
        # ("5 Aashirvaad Atta 4600" with no unit at all would also land here).
        rest = f"{unit_token} {rest}".strip()

    name, price_paise = _split_name_price(rest)

    try:
        qty = float(qty_raw)
        if qty.is_integer():
            qty = int(qty)
    except ValueError:
        qty = 0

    return {
        "name": name.lower(),
        "qty": qty,
        "unit": unit,
        "price_paise": price_paise,
        "_source": "rule",
    }


def _detect_lang(text: str) -> str:
    if _DEVANAGARI_RE.search(text):
        return "hi"
    if _KANNADA_RE.search(text):
        return "kn"
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    return "hi" if words & _HINDI_ROMAN_CUES else "en"


def _detect_intent(text: str) -> str:
    lowered = f" {text.lower()} "
    if any(f" {w} " in lowered or lowered.strip().startswith(w) for w in _QUERY_WORDS):
        return "query"
    if any(w in lowered for w in _STOCK_OUT_WORDS):
        return "stock_out"
    if any(w in lowered for w in _STOCK_IN_WORDS):
        return "stock_in"
    return "query"


def extract_message(text: str) -> dict:
    """A typed sentence -> {"intent", "lang", "items", "_source": "rule"}.

    Query vs. stock-write is decided by explicit keyword cues only -- a sentence with
    no recognised verb defaults to "query" rather than risk writing stock from a
    sentence this module doesn't understand. That mirrors the stricter of the two
    failure directions: a missed query is a shrug, a phantom stock write corrupts the
    books. A query's "items" entry (if any) carries a name only, qty=0 -- it's there
    for the caller to look up and answer with, never to write.
    """
    intent = _detect_intent(text)
    lang = _detect_lang(text)

    items: list[dict] = []
    if intent == "query":
        # A query carries no qty/unit to write -- only an item name, for the caller to
        # look up and answer with (see docs/api-contract.md's /api/chat example: the
        # reply states a real stock level, which requires knowing which SKU is being
        # asked about even though nothing gets written). Strip query-cue filler and
        # unit words; whatever alphabetic tokens remain are the probable item name.
        words = [
            w for w in re.findall(r"[a-zA-Z]+", text.lower())
            if w not in _QUERY_FILLER_WORDS and w.lower() not in _UNIT_LOOKUP
        ]
        if words:
            items.append({"name": " ".join(words), "qty": 0, "unit": None, "price_paise": None})
    else:
        # Look for a <qty> <unit> <name> fragment anywhere in the sentence rather than
        # anchoring the whole line, since real messages have surrounding words.
        m = re.search(r"(?P<qty>\d+(?:\.\d+)?)\s*(?P<unit>[a-zA-Z]+)?\s+(?P<name>[a-zA-Z][a-zA-Z \-]*)", text)
        if m:
            unit = _lookup_unit(m.group("unit"))
            name = m.group("name").strip().lower()
            if unit is None and m.group("unit"):
                name = f"{m.group('unit')} {name}".strip().lower()
            try:
                qty = float(m.group("qty"))
                if qty.is_integer():
                    qty = int(qty)
            except ValueError:
                qty = 0
            items.append({"name": name, "qty": qty, "unit": unit, "price_paise": None})

    return {
        "intent": intent,
        "lang": lang,
        "items": items,
        "_source": "rule",
    }
