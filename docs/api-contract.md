# API Contract — FROZEN

Read this together, out loud, before anyone writes code. Change anything that looks wrong
**now**. After that, nobody changes a field name without telling the other three.

Changing a field name at hour two costs far more than it looks like it should.

---

## The shape of the thing

Two calls, and the split between them is the whole design:

| Call | Writes to the database? |
|---|---|
| `POST /api/scan` | **No.** Reads the bill, resolves items, returns a review payload. |
| `POST /api/scan/confirm` | **Yes.** The only endpoint that touches the ledger. |

Abandoning a scan costs nothing. Nothing is committed until a human approves it.

---

## `POST /api/scan`

Multipart only — there's always an image.

| Field | Type | Notes |
|---|---|---|
| `shop_id` | int | Required |
| `sender` | string | Required. Per-tab id from `sessionStorage` |
| `image` | file | Required. The bill photo |

**The browser downscales to 1024 px on the longest edge before uploading.** The server
re-does it as a guard, but doing it client-side keeps uploads fast on venue wifi.

Upload cap: **15 MB** → `413`.

### Response — 200, bill read successfully

```json
{
  "scan_id": 14,
  "legible": true,
  "confidence": "high",
  "script": "latin",
  "raw_text": "20 pkt Parle-G 480\n2 dzn Maggi 240\n5 kg Aashirvaad Atta 4600",
  "reply": "Bill mein 3 item mile. Check karke confirm kijiye.",
  "lang": "hi",
  "items": [
    {
      "line_index": 0,
      "line": "20 pkt Parle-G 480",
      "name": "parle-g",
      "qty": 20,
      "unit": "packet",
      "unit_ok": true,
      "price_paise": 480,
      "resolution": {
        "status": "exact",
        "sku_id": 3,
        "sku_name": "Parle-G Biscuit",
        "candidates": []
      }
    },
    {
      "line_index": 1,
      "line": "2 dzn Maggi 240",
      "name": "maggi",
      "qty": 2,
      "unit": "dozen",
      "unit_ok": true,
      "price_paise": 240,
      "resolution": {
        "status": "ambiguous",
        "sku_id": null,
        "sku_name": null,
        "candidates": [
          { "sku_id": 11, "name": "Maggi Noodles 70g", "score": 91 },
          { "sku_id": 12, "name": "Maggi Masala 100g", "score": 88 }
        ]
      }
    }
  ],
  "warnings": ["line 3: unit \"bdl\" not recognised"],
  "debug": { "extract_source": "llm", "ocr_ms": 5200, "total_ms": 6100 }
}
```

### Field meanings

| Field | Notes |
|---|---|
| `scan_id` | Pass this back to `/confirm`. Valid until confirmed or abandoned. |
| `legible` | `false` when the photo isn't a bill or can't be read. Then `items` is empty and `reply` explains. **The frontend must handle this case first.** |
| `confidence` | `"low"` on a handwritten or poor-quality read. The UI shows a "check carefully" banner. |
| `raw_text` | The full transcription. **Display it** — on a handwritten bill the shopkeeper needs to see what was read. |
| `unit_ok` | `false` when `units.normalize_unit` returned `None`. Not an error — the row needs a unit picked in the UI. |
| `resolution.status` | `exact` \| `fuzzy` \| `ambiguous` \| `unknown` |
| `candidates` | Populated on `ambiguous`. The UI renders these as a dropdown. |
| `price_paise` | **Integer paise.** 480 means ₹4.80. `null` if the bill didn't state one. |
| `debug.extract_source` | `"llm"` or `"rule"`. Surfaces a silent fallback in the response. |

### How the frontend renders each status

| Status | UI |
|---|---|
| `exact` | Green tick, SKU name shown, pre-ticked for booking |
| `fuzzy` | Amber, SKU name shown, pre-ticked, but changeable |
| `ambiguous` | **Dropdown of `candidates`**, nothing pre-selected. Must be chosen or skipped. |
| `unknown` | "Create new item" option, or skip |
| `unit_ok: false` | Unit dropdown on that row, from the eight canonical units |

---

## `POST /api/scan/confirm`

JSON. This is the only call that writes.

```json
{
  "shop_id": 1,
  "scan_id": 14,
  "decisions": [
    { "line_index": 0, "action": "book", "sku_id": 3, "qty": 20, "unit": "packet", "price_paise": 480 },
    { "line_index": 1, "action": "book", "sku_id": 11, "qty": 2, "unit": "dozen", "price_paise": 240 },
    { "line_index": 2, "action": "skip" },
    { "line_index": 3, "action": "new", "name": "Local Soap Bar", "unit": "piece", "qty": 12, "price_paise": 1500 }
  ]
}
```

`action` is one of:

| Action | Effect |
|---|---|
| `book` | Write the movement against `sku_id`. If the line was `ambiguous` or `unknown`, **also write an alias** so the same bill text resolves silently next time. |
| `skip` | Nothing written for that line |
| `new` | `create_sku`, then book against it, then write the alias |

The client sends `qty`, `unit` and `price_paise` back even when unchanged — the shopkeeper may
have edited them in the review table, and the server trusts the confirmed values over what it
originally parsed.

### Response — 200

```json
{
  "reply": "7 item likh diye. Parle-G ab 34 packet.",
  "lang": "hi",
  "actions": [
    { "sku_id": 3, "sku_name": "Parle-G Biscuit", "direction": "stock_in",
      "qty": 20, "unit": "packet", "new_qty": 34 }
  ],
  "aliases_learned": [{ "text": "maggi", "sku_id": 11 }],
  "skipped": 1
}
```

`aliases_learned` is worth showing in the UI — "I'll remember 'maggi' means Maggi Noodles
next time" is the ask-once promise made visible, and it's the line that sells the demo.

### Errors

| Status | When |
|---|---|
| 400 | Bad `shop_id`, unknown `scan_id`, malformed `decisions` |
| 409 | **Scan already confirmed.** A double-tap on Confirm must not book the bill twice. |
| 413 | Upload over 15 MB (on `/api/scan`) |
| 422 | A `book` decision with no `sku_id`, or a `new` with no `name` |
| 500 | Anything unexpected — still shaped `{"error": ...}` |

**Always a real status code with an error body.** Never a 200 with an error inside, never a
bare crash.

```json
{ "error": "scan 14 already confirmed" }
```

**`apply_scan` is one transaction.** Ten rows are all-or-nothing — row seven failing must not
leave six committed.

---

## `POST /api/chat`

Secondary surface: typed text for queries and corrections. Keeps the multilingual
demonstration alive without a camera.

### Request

```json
{ "shop_id": 1, "sender": "web-abc123", "text": "kitna parle g bacha hai" }
```

### Response

```json
{
  "reply": "Parle-G Biscuit ka abhi 34 packet hai, karib 6 din chalega.",
  "lang": "hi",
  "actions": [],
  "debug": { "extract_source": "llm", "detected_lang": "hi" }
}
```

**A query never writes.** Only `stock_in` / `stock_out` intents reach the resolver; a
`query` intent goes to a lookup. `"2 kg aata chahiye"` parses as a clean item but is a
request — it must not move stock.

---

## `GET /api/inventory?shop_id=1`

```json
{
  "items": [
    { "sku_id": 3, "name": "Parle-G Biscuit", "qty": 34, "unit": "packet",
      "cost_per_unit": 480, "days_of_cover": 6.2, "low": false }
  ]
}
```

`cost_per_unit` is **integer paise** — the frontend divides by 100. `days_of_cover` is `null`
when there's no sales history. `low` is the backend's call; the frontend just paints the row.

---

## Conventions that bind everyone

- **Money is integer paise everywhere**, API and database. Never float rupees.
- **`unit` is always one of:** `packet`, `box`, `sack`, `dozen`, `kg`, `gram`, `litre`,
  `piece`. The extraction schema enforces this by enum.
- **Item names crossing module boundaries are Latin script, lowercase.** Kannada and
  Devanagari are transliterated during OCR. Display names (`sku_name`) keep proper casing.
- **`sender` is per-tab**, from `sessionStorage`.
- The frontend escapes everything it renders from the API — OCR text especially, since it
  comes from an image via a model. `escapeHtml`, never raw `innerHTML`.
- **Images are downscaled client-side before upload.** 1024 px longest edge.

---

## Stub responses

Ayush Rai: build the whole review UI against these from minute one. They're the shapes above
with fixed values, so the UI keeps working unchanged when the real pipeline lands.

Return the three-item example above for any uploaded image — one `exact`, one `ambiguous`,
one with `unit_ok: false`. That single fixture exercises every branch of the review table,
which is the most complex piece of frontend in the project.

Also stub one `legible: false` response behind a query flag (`?fail=1`) so the unreadable-photo
path gets built rather than discovered during the demo.
