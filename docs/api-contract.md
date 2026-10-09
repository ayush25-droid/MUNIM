# API Contract — FROZEN

Read this together, out loud, before anyone writes code. Change anything that looks wrong
**now**. After that, nobody changes a field name without telling the other three.

Changing a field name at hour three costs far more than it looks like it should.

---

## `POST /api/chat`

Accepts **either** JSON or multipart. Both are supported from the start — the frontend uses
JSON for typed text and multipart when there's a voice note or photo attached.

### Request — JSON

```json
{ "shop_id": 1, "sender": "web-abc123", "text": "do amul aaye" }
```

### Request — multipart/form-data

| Field | Type | Notes |
|---|---|---|
| `shop_id` | int | Required |
| `sender` | string | Required. Per-tab id from `sessionStorage`, **not** a shared constant — two tabs must not share pending-question state |
| `text` | string | Optional |
| `audio` | file | Optional. Voice note |
| `image` | file | Optional. Bill photo |

Upload cap: **15 MB**. A bill photo's extracted text must **not** silently overwrite
`text` if both are sent.

### Response — 200

```json
{
  "reply": "Likh diya - 20 packet Parle-G, 5 kg aata.",
  "lang": "hi",
  "actions": [
    { "sku_id": 3, "sku_name": "Parle-G Biscuit", "direction": "stock_in",
      "qty": 20, "unit": "packet" }
  ],
  "options": [],
  "debug": { "extract_source": "llm", "detected_lang": "hi", "ms": 1840 }
}
```

| Field | Meaning |
|---|---|
| `reply` | The text to show in the bot bubble. Already in the user's language. |
| `lang` | `en` \| `hi` \| `kn` — what the agent detected |
| `actions` | What was actually written to the ledger. Empty on a question or a query. |
| `options` | Present **only** when the agent is asking something. Empty array otherwise. |
| `debug.extract_source` | `"llm"` or `"rule"`. Surfaces a silent fallback in the response rather than only in a log nobody is watching. |

### Asking a question

```json
{
  "reply": "Amul Butter ya Amul Milk? (ya naya item hai?)",
  "lang": "hi",
  "actions": [],
  "options": [
    { "label": "Amul Butter", "value": "sku:7" },
    { "label": "Amul Milk",   "value": "sku:9" },
    { "label": "Naya item",   "value": "new" },
    { "label": "Cancel",      "value": "cancel" }
  ],
  "debug": { "extract_source": "llm", "detected_lang": "hi", "ms": 1620 }
}
```

**The frontend sends `value`, never `label`.** Sending the label means the backend receives
`"Amul Butter"` when it expects `"sku:7"`.

The backend must **also** accept the answer typed as free text (`butter`, `haan`, `nahi`,
`new`, `cancel`) — a WhatsApp user has no buttons. So `reply` spells the choices out in
words as well.

### Errors

Always a real status code with an error body. **Never a 200 with an error inside, and never
a bare crash.**

```json
{ "error": "unknown shop_id" }
```

| Status | When |
|---|---|
| 400 | Bad or missing `shop_id` / `sender`, unparseable body |
| 413 | Upload over 15 MB |
| 500 | Anything unexpected — still shaped `{"error": ...}` |

---

## `GET /api/inventory?shop_id=1`

```json
{
  "items": [
    { "sku_id": 3, "name": "Parle-G Biscuit", "qty": 14, "unit": "packet",
      "cost_per_unit": 480, "days_of_cover": 3.9, "low": true }
  ]
}
```

| Field | Notes |
|---|---|
| `cost_per_unit` | **Integer paise.** 480 means ₹4.80. The frontend divides by 100 to display. |
| `days_of_cover` | Float, or `null` when there's no sales history for that SKU |
| `low` | Boolean. The backend decides the threshold — the frontend just paints the row red. |

---

## Conventions that bind everyone

- **Money is integer paise everywhere**, in the API and in the database. Never float rupees.
- **`unit` is always one of:** `packet`, `box`, `sack`, `dozen`, `kg`, `gram`, `litre`,
  `piece`. The extraction schema enforces this by enum.
- **Item names crossing module boundaries are Latin script, lowercase.** Kannada and
  Devanagari are transliterated at extraction. Display names (`sku_name`) keep their proper
  casing.
- **`sender` is per-tab**, from `sessionStorage`. Pending-question state is keyed on it.
- The frontend escapes everything it renders from the API. Catalogue text and option labels
  go through `escapeHtml`, never raw `innerHTML`.

---

## Stub responses

Ayush Rai: build the frontend against these from minute one. They are the shapes above with
fixed values, so the UI keeps working unchanged when the real pipeline lands.

Return a confirmation for any message containing `aaye`, the question block for anything
containing `amul`, and `not_understood` otherwise. That is enough to build and demo the
entire chat flow before the model is wired up.
