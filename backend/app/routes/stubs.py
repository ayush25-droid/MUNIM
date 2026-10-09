"""Canned responses copied from docs/api-contract.md. One fixture exercises every review-table branch."""
import copy

_SCAN = {
    "scan_id": 14,
    "legible": True,
    "confidence": "high",
    "script": "latin",
    "raw_text": "20 pkt Parle-G 480\n2 dzn Maggi 240\n3 bdl Local Soap 1500",
    "reply": "Bill mein 3 item mile. Check karke confirm kijiye.",
    "lang": "hi",
    "items": [
        {"line_index": 0, "line": "20 pkt Parle-G 480", "name": "parle-g", "qty": 20,
         "unit": "packet", "unit_ok": True, "price_paise": 480,
         "resolution": {"status": "exact", "sku_id": 3, "sku_name": "Parle-G Biscuit", "candidates": []}},
        {"line_index": 1, "line": "2 dzn Maggi 240", "name": "maggi", "qty": 2,
         "unit": "dozen", "unit_ok": True, "price_paise": 240,
         "resolution": {"status": "ambiguous", "sku_id": None, "sku_name": None, "candidates": [
             {"sku_id": 11, "name": "Maggi Noodles 70g", "score": 91},
             {"sku_id": 12, "name": "Maggi Masala 100g", "score": 88}]}},
        {"line_index": 2, "line": "3 bdl Local Soap 1500", "name": "local soap", "qty": 3,
         "unit": None, "unit_ok": False, "price_paise": 1500,
         "resolution": {"status": "unknown", "sku_id": None, "sku_name": None, "candidates": []}},
    ],
    "warnings": ['line 3: unit "bdl" not recognised'],
    "debug": {"extract_source": "llm", "ocr_ms": 5200, "total_ms": 6100},
}

_ILLEGIBLE = {
    "scan_id": None, "legible": False, "confidence": "low", "script": "latin", "raw_text": "",
    "reply": "Yeh photo padh nahi paya. Bill saaf roshni mein dobara kheenchiye.",
    "lang": "hi", "items": [], "warnings": [],
    "debug": {"extract_source": "llm", "ocr_ms": 3000, "total_ms": 3100},
}

_CONFIRM = {
    "reply": "2 item likh diye. Parle-G ab 34 packet.",
    "lang": "hi",
    "actions": [{"sku_id": 3, "sku_name": "Parle-G Biscuit", "direction": "stock_in",
                 "qty": 20, "unit": "packet", "new_qty": 34}],
    "aliases_learned": [{"text": "maggi", "sku_id": 11}],
    "skipped": 1,
}

_CHAT = {
    "reply": "Parle-G Biscuit ka abhi 34 packet hai, karib 6 din chalega.",
    "lang": "hi", "actions": [],
    "debug": {"extract_source": "llm", "detected_lang": "hi"},
}

_INVENTORY = {"items": [
    {"sku_id": 3, "name": "Parle-G Biscuit", "qty": 34, "unit": "packet",
     "cost_per_unit": 480, "days_of_cover": 6.2, "low": False},
    {"sku_id": 11, "name": "Maggi Noodles 70g", "qty": 3, "unit": "packet",
     "cost_per_unit": 1200, "days_of_cover": 0.8, "low": True},
    {"sku_id": 12, "name": "Maggi Masala 100g", "qty": 18, "unit": "packet",
     "cost_per_unit": 1400, "days_of_cover": None, "low": False},
]}


def scan(fail: bool = False) -> dict:
    return copy.deepcopy(_ILLEGIBLE if fail else _SCAN)


def confirm() -> dict:
    return copy.deepcopy(_CONFIRM)


def chat() -> dict:
    return copy.deepcopy(_CHAT)


def inventory() -> dict:
    return copy.deepcopy(_INVENTORY)
