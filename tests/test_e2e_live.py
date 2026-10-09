import json
import os
import sys

# Ensure backend is on sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app import db, seed, pipeline

print("Resetting and seeding demo database...")
seed.seed(reset=True)

bill_path = "tests/bills/handwritten-01.jpg"
print(f"\n1. Scanning handwritten bill ({bill_path})...")
with open(bill_path, "rb") as f:
    img_bytes = f.read()

scan1 = pipeline.scan_bill(1, img_bytes)
print(f"Scan ID: {scan1['scan_id']}")
print(f"Confidence: {scan1['confidence']}")
print(f"OCR latency: {scan1['debug']['ocr_ms']}ms, Total latency: {scan1['debug']['total_ms']}ms")
print("Items parsed and initial resolutions:")
for it in scan1["items"]:
    status = it["resolution"]["status"]
    sku = it["resolution"]["sku_name"] or "None"
    cands = [c["name"] for c in it["resolution"]["candidates"]]
    print(f"  Line {it['line_index']}: '{it['line']}' -> status={status}, sku='{sku}', candidates={cands}")

print("\n2. Confirming bill (resolving ambiguous items)...")
decisions = [
    {"line_index": 0, "action": "book", "sku_id": 1, "qty": 20, "unit": "packet", "price_paise": 480},
    {"line_index": 1, "action": "book", "sku_id": 3, "qty": 2, "unit": "dozen", "price_paise": 240}, # Maggi Noodles 70g
    {"line_index": 2, "action": "book", "sku_id": 5, "qty": 5, "unit": "sack", "price_paise": 4600}, # Aashirvaad Atta
    {"line_index": 3, "action": "book", "sku_id": 9, "qty": 10, "unit": "piece", "price_paise": 280},
    {"line_index": 4, "action": "book", "sku_id": 12, "qty": 1, "unit": "box", "price_paise": 720},
]

conf = pipeline.confirm_scan(1, scan1["scan_id"], decisions)
print("Confirm response:")
print(f"  Reply: {conf['reply']}")
print(f"  Actions recorded: {len(conf['actions'])}")
print(f"  Aliases learned: {conf['aliases_learned']}")

print("\n3. Testing 409 idempotency (re-confirming the same scan)...")
try:
    pipeline.confirm_scan(1, scan1["scan_id"], decisions)
    print("ERROR: Should have thrown 409 Conflict!")
except Exception as e:
    print(f"  Successfully caught duplicate confirm: {type(e).__name__} -> {e}")

print("\n4. Re-scanning the EXACT same handwritten bill to verify 'Ask-Once'...")
scan2 = pipeline.scan_bill(1, img_bytes)
print("Re-scan resolutions:")
all_exact = True
for it in scan2["items"]:
    status = it["resolution"]["status"]
    sku = it["resolution"]["sku_name"]
    print(f"  Line {it['line_index']}: '{it['line']}' -> status={status}, sku='{sku}'")
    if status != "exact":
        all_exact = False

if all_exact:
    print("\nSUCCESS: All items resolved as EXACT without asking! 'Ask-Once' verified on live hardware!")
else:
    print("\nNote: Some items still not exact.")
