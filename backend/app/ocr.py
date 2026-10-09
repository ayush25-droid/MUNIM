"""Bill photo -> plain text lines.

Deliberately does NOT emit final structured items -- it transcribes the bill into one
line per item, transliterated to Latin script. Those lines then go through the normal
extract -> resolve path, same as typed text (see IMPLEMENTATION.md, "the two decisions
everything follows from").

The non-bill / illegible guard matters as much as correct transcription: a hallucinated
delivery from a photo of a wall is the single worst output this module can produce.
"""
from __future__ import annotations

from . import llm

BILL_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {"type": "array", "items": {"type": "string"}},
        "raw_text": {"type": "string"},
        "script": {
            "type": "string",
            "enum": ["latin", "devanagari", "kannada", "mixed"],
        },
        "legible": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["high", "low"]},
    },
    "required": ["lines", "raw_text", "script", "legible", "confidence"],
}

BILL_PROMPT = """You are reading a photo of a supplier bill for an Indian kirana (small
grocery) shop. The bill may be printed or handwritten, and may be in English, Hindi
(Devanagari), or Kannada script, or a mix.

Transcribe it into one line per item, in this exact shape:
  <qty> <unit> <item name> <price if present>

Rules, follow them exactly:
1. One item per line. Do not merge multiple items into one line or split one item
   across two lines.
2. Transliterate every item name into LATIN SCRIPT, regardless of what script the bill
   is written in. "ಪಾರ್ಲೆ-ಜಿ" and "पारले जी" both become "parle g". Do not translate the
   meaning -- transliterate the sound.
3. Prices are plain numbers only, no currency symbols, no commas ("4600" not "Rs.4,600"
   or "₹4,600").
4. If a line is illegible or you are not confident what it says, SKIP that line rather
   than guessing at it. A skipped line is fine; an invented one is not.
5. If the photo is not a bill at all (a wall, a product, a face, a blank page, anything
   that isn't an itemized bill), or if it is too illegible to read as a bill, set
   "legible" to false, leave "lines" empty, and do not invent any items. This is the
   single most important rule here: a hallucinated delivery is worse than admitting you
   cannot read the photo.
6. Set "confidence" to "low" if the bill is handwritten, blurry, at a bad angle, or
   otherwise hard to read, even if you did produce lines. Set it to "high" only for a
   clearly legible printed bill.
7. Set "script" to whichever of latin/devanagari/kannada/mixed the ORIGINAL bill text
   was written in (before your transliteration).
8. "raw_text" is the full transcription as you read it (one line per item, same as
   "lines"), for display to the shopkeeper.

Return only the JSON object matching the given schema."""


def read_bill(image: bytes) -> dict:
    """Read a (prepared) bill photo and return the transcription.

    Returns:
        {
          "lines": [str, ...],
          "raw_text": str,
          "script": "latin" | "devanagari" | "kannada" | "mixed",
          "legible": bool,
          "confidence": "high" | "low",
        }

    Never raises -- an LLM failure or a malformed response comes back as an honest
    `legible: false` rather than propagating up and failing the whole scan.
    """
    try:
        result = llm.generate(
            BILL_PROMPT,
            schema=BILL_SCHEMA,
            images=[image],
            timeout=llm.LLM_VISION_TIMEOUT,
        )
    except llm.LLMError:
        return _illegible_result()

    if not isinstance(result, dict):
        return _illegible_result()

    legible = bool(result.get("legible", False))
    raw_lines = result.get("lines") or []
    lines = [str(line).strip() for line in raw_lines if str(line).strip()] if legible else []

    script = result.get("script")
    if script not in ("latin", "devanagari", "kannada", "mixed"):
        script = "mixed"

    confidence = result.get("confidence")
    if confidence not in ("high", "low"):
        confidence = "low"

    # A "legible" bill with zero usable lines is functionally the same as illegible --
    # don't let the pipeline proceed to extraction on nothing.
    if legible and not lines:
        legible = False

    return {
        "lines": lines,
        "raw_text": str(result.get("raw_text") or ""),
        "script": script,
        "legible": legible,
        "confidence": confidence,
    }


def _illegible_result() -> dict:
    return {
        "lines": [],
        "raw_text": "",
        "script": "latin",
        "legible": False,
        "confidence": "low",
    }
