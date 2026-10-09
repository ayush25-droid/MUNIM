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


def scan_summary(items: list[dict], lang: str) -> str:
    count = len(items)
    needs_attention = sum(
        1 for i in items
        if i.get("resolution", {}).get("status") in ("ambiguous", "unknown")
        or not i.get("unit_ok", True)
    )

    if count == 0:
        return {
            "hi": "Bill mein koi item nahi mila.",
            "kn": "ಬಿಲ್‌ನಲ್ಲಿ ಯಾವುದೇ ಐಟಂ ಸಿಗಲಿಲ್ಲ.",
        }.get(lang, "No items found on the bill.")

    if lang == "hi":
        base = f"Bill mein {count} item mile."
        if needs_attention:
            return f"{base} {needs_attention} ko check karke confirm kijiye."
        return f"{base} Check karke confirm kijiye."

    if lang == "kn":
        base = f"ಬಿಲ್‌ನಲ್ಲಿ {count} ಐಟಂ ಸಿಕ್ಕಿವೆ."
        if needs_attention:
            return f"{base} {needs_attention} ಐಟಂ ಪರಿಶೀಲಿಸಿ."
        return f"{base} ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಖಚಿತಪಡಿಸಿ."

    base = f"Found {count} item{'s' if count != 1 else ''} on the bill."
    if needs_attention:
        return f"{base} {needs_attention} need your input before confirming."
    return f"{base} Review and confirm."


def confirm_summary(actions: list[dict], lang: str) -> str:
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
