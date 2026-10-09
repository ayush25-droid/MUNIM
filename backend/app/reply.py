"""Reply text in en / hi / kn. Short and friendly, matching the tone in
docs/api-contract.md's examples ("Bill mein 3 item mile. Check karke confirm kijiye.").

Kannada strings here are a first pass, not verified by a native speaker -- same
disclosed-limitation posture as the rest of the Kannada path (see tests/corpus.md,
"Kannada unit vocabulary to verify"). Flag corrections the same way.

Includes one function beyond the three in IMPLEMENTATION.md's original list --
`stock_query_answer` -- which pipeline.handle_message needs for the "query" intent to
actually answer with a stock level (per docs/api-contract.md's /api/chat example)
rather than just restate that it heard a question. The original three didn't cover
that case.
"""
from __future__ import annotations


def scan_summary(items: list[dict], lang: str, direction: str = "stock_in") -> str:
    count = len(items)
    needs_attention = sum(
        1 for i in items
        if i.get("resolution", {}).get("status") in ("ambiguous", "unknown")
        or not i.get("unit_ok", True)
    )
    # Only a selling bill gets a prefix -- stock_in is the original, unannounced
    # default, so its wording stays exactly what it was before direction existed.
    note = _direction_note(direction, lang)

    if count == 0:
        text = {
            "hi": "Bill mein koi item nahi mila.",
            "kn": "ಬಿಲ್‌ನಲ್ಲಿ ಯಾವುದೇ ಐಟಂ ಸಿಗಲಿಲ್ಲ.",
        }.get(lang, "No items found on the bill.")
        return f"{note} {text}" if note else text

    if lang == "hi":
        base = f"Bill mein {count} item mile."
        text = f"{base} {needs_attention} ko check karke confirm kijiye." if needs_attention \
            else f"{base} Check karke confirm kijiye."
    elif lang == "kn":
        base = f"ಬಿಲ್‌ನಲ್ಲಿ {count} ಐಟಂ ಸಿಕ್ಕಿವೆ."
        text = f"{base} {needs_attention} ಐಟಂ ಪರಿಶೀಲಿಸಿ." if needs_attention \
            else f"{base} ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಖಚಿತಪಡಿಸಿ."
    else:
        base = f"Found {count} item{'s' if count != 1 else ''} on the bill."
        text = f"{base} {needs_attention} need your input before confirming." if needs_attention \
            else f"{base} Review and confirm."

    return f"{note} {text}" if note else text


def _direction_note(direction: str, lang: str) -> str:
    """A short heads-up that stock will go DOWN, said only for a selling bill --
    the shopkeeper confirming a sale needs to know that up front, the same way the
    review table's qty/price are shown before anything is written. Silent for
    stock_in since that's the original, long-verified default behaviour.
    """
    if direction != "stock_out":
        return ""
    return {
        "hi": "Yeh bikri ka bill hai, stock kam hoga.",
        "kn": "ಇದು ಮಾರಾಟದ ಬಿಲ್, ಸ್ಟಾಕ್ ಕಡಿಮೆಯಾಗುತ್ತದೆ.",
    }.get(lang, "This is a selling bill, stock will go down.")


def confirm_summary(actions: list[dict], lang: str, direction: str = "stock_in") -> str:
    count = len(actions)
    if count == 0:
        return {
            "hi": "Kuch bhi nahi likha gaya.",
            "kn": "ಏನೂ ದಾಖಲಿಸಲಾಗಿಲ್ಲ.",
        }.get(lang, "Nothing was booked.")

    headline = actions[0]
    tail = ""
    if headline.get("sku_name") and headline.get("new_qty") is not None:
        if lang == "hi":
            tail = f" {headline['sku_name']} ab {headline['new_qty']} {headline.get('unit', '')}."
        elif lang == "kn":
            tail = f" {headline['sku_name']} ಈಗ {headline['new_qty']} {headline.get('unit', '')}."
        else:
            tail = f" {headline['sku_name']} is now {headline['new_qty']} {headline.get('unit', '')}."

    # Same silent-for-stock_in rule as scan_summary's _direction_note -- unchanged
    # wording for the long-verified default, a short "sold" prefix for the new path.
    if direction == "stock_out":
        if lang == "hi":
            return f"{count} item becha gaya.{tail}"
        if lang == "kn":
            return f"{count} ಐಟಂ ಮಾರಾಟವಾಗಿದೆ.{tail}"
        return f"{count} item{'s' if count != 1 else ''} sold.{tail}"

    if lang == "hi":
        return f"{count} item likh diye.{tail}"
    if lang == "kn":
        return f"{count} ಐಟಂ ದಾಖಲಿಸಲಾಗಿದೆ.{tail}"
    return f"{count} item{'s' if count != 1 else ''} booked.{tail}"


def illegible(lang: str) -> str:
    return {
        "hi": "Yeh bill padh nahi paya. Saaf photo try kijiye.",
        "kn": "ಈ ಬಿಲ್ ಓದಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಸ್ಪಷ್ಟವಾದ ಫೋಟೋ ಪ್ರಯತ್ನಿಸಿ.",
    }.get(lang, "Couldn't read that as a bill. Try a clearer photo.")


def stock_query_answer(rows: list[dict], lang: str) -> str:
    """`rows` is a list of {"name", "qty", "unit", "days_of_cover"} for the SKU(s) a
    query resolved to. Empty list means nothing matched (unknown item, or no item
    named at all) -- answered honestly rather than inventing a number.
    """
    if not rows:
        return {
            "hi": "Yeh item nahi mila. Naam check karke phir poochiye.",
            "kn": "ಈ ಐಟಂ ಸಿಗಲಿಲ್ಲ. ಹೆಸರು ಪರಿಶೀಲಿಸಿ ಮತ್ತೆ ಕೇಳಿ.",
        }.get(lang, "Couldn't find that item. Check the name and ask again.")

    row = rows[0]
    cover = row.get("days_of_cover")
    cover_hi = f", karib {cover} din chalega" if cover is not None else ""
    cover_kn = f", ಸುಮಾರು {cover} ದಿನ ಸಾಕಾಗುತ್ತದೆ" if cover is not None else ""
    cover_en = f", about {cover} days of cover left" if cover is not None else ""

    if lang == "hi":
        return f"{row['name']} ka abhi {row['qty']} {row['unit']} hai{cover_hi}."
    if lang == "kn":
        return f"{row['name']} ಈಗ {row['qty']} {row['unit']} ಇದೆ{cover_kn}."
    return f"{row['name']} has {row['qty']} {row['unit']} left{cover_en}."


def insufficient_stock(name: str, have: float, need: float, unit: str, lang: str) -> str:
    """A stock_out that can't be fulfilled -- inventory.InsufficientStockError
    blocks the write itself, this just says so in words instead of a raw
    exception message, matching the rest of this file's tone.
    """
    if lang == "hi":
        return f"{name} ka stock kam hai (sirf {have} {unit}) -- {need} {unit} ki sale nahi ho sakti."
    if lang == "kn":
        return f"{name} ಸ್ಟಾಕ್ ಕಡಿಮೆ ಇದೆ (ಕೇವಲ {have} {unit}) -- {need} {unit} ಮಾರಾಟ ಸಾಧ್ಯವಿಲ್ಲ."
    return f"Not enough {name} in stock (only {have} {unit} left) -- can't sell {need} {unit}."
