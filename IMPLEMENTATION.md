# Implementation Guide

Read this before writing a line. It defines the architecture, the hard hardware limit, and
the exact contract between every module so four people can build in parallel without
waiting on each other.

---

## What we're building

**The shopkeeper photographs a supplier bill. The inventory updates.**

Bills are handwritten or printed. The agent reads the photo, works out which catalogue item
each line refers to, shows the shopkeeper what it understood, and commits to the ledger only
after they confirm.

No WhatsApp. It's a web app — the shopkeeper opens a page, taps the camera, done.

### Why the confirm step exists, and why it isn't a weakness

A bill writes **many rows at once**, and handwritten OCR is imperfect. Blindly committing
ten ledger entries from a possibly-misread photo is exactly the failure this whole design
exists to prevent: a wrong number that looks right and corrupts the books silently.

So the scan is **read-only**. It parses, resolves, and presents. Nothing is written until the
shopkeeper confirms. That human-approval gate is the strongest thing in the demo — it shows
an agent that knows the difference between confidence and certainty.

---

## The two decisions everything follows from

**1 — One model does everything.** `gemma4:latest` on the 4060 reports
`["completion", "vision", "audio", "tools", "thinking"]`. Vision and text extraction come
from the same loaded model, so there is no second model to fit in VRAM.

**2 — Vision flattens to text, then the normal pipeline runs.** The vision call does *not*
emit final structured data. It transcribes the bill into plain text lines. Those lines go
through the same extraction → resolve → write path as typed text.

Three reasons this beats one-shot structured vision:

- The rule-based fallback extractor still applies, so a vision read that produces text but
  confuses the model's JSON still lands somewhere useful.
- One code path to debug instead of two.
- The intermediate transcript is **showable and editable**. On a handwritten bill the
  shopkeeper can fix a misread line before anything is committed.

---

## Hardware limit — the binding constraint

One inference box: **Ayush Aditya's RTX 4060 laptop** at `http://172.1.58.57:11434`. The
model lives there, final integration happens there, and the demo runs from there. Everyone
else develops against it over the LAN.

```
Total VRAM                      8.0 GiB
Available (reported by Ollama)  6.9 GiB
gemma4:latest  Q4_K_M weights  ~6.1 GiB
KV cache @ num_ctx 4096        ~0.3-0.5 GiB
                               ----------
                               ~6.5 GiB   leaves ~400 MiB
```

**Five rules. Breaking any one of them kills the demo.**

1. **Never load a second model.** `OLLAMA_MAX_LOADED_MODELS=1` on the server. Don't pull a
   "quick comparison" model and leave it resident.
2. **Keep `num_ctx` at 4096.** The model advertises 131072. Requesting anything close
   allocates a KV cache many times the free VRAM and fails instantly.
3. **Downscale every image to 1024 px on the longest edge before sending.** This is now the
   most important rule in the file. A raw 12 MP phone photo encodes to thousands of image
   tokens, which blows the context window *and* makes inference crawl. 1024 px is plenty to
   read a bill. Do it in the browser before upload, and again server-side as a guard.
4. **Disable `thinking`.** Extended reasoning costs seconds we don't have.
5. **Set `keep_alive: "30m"`** so the model isn't unloaded between requests. A cold load is
   20–40 s and looks like a hang during judging.

**Vision needs working memory beyond the figures above.** Test an actual bill photo early —
don't assume the 400 MiB margin absorbs it. If it OOMs: drop `num_ctx` to 2048 first, then
downscale images to 768 px.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Inference | Ollama on the 4060, `gemma4:latest` | Already installed and pulled, no download risk |
| Backend | Python 3.11+, FastAPI | Fast to write |
| Database | SQLite | No service to provision |
| Matching | `rapidfuzz` | Deterministic, fast. `difflib` if pip fails |
| Image prep | `Pillow` | Downscale + EXIF rotation. One dependency, non-negotiable |
| Frontend | Plain HTML + CSS + vanilla JS | No build step, no CDN that dies with venue wifi |

Everything runs on the 4060 laptop for the demo. The other three develop locally against the
same Ollama endpoint over the LAN.

---

## File tree and ownership

Nobody edits a file they don't own.

```
MUNIM/
  backend/
    requirements.txt
    app/
      __init__.py
      llm.py            Ollama adapter                      -> Ayush Rai
      imageprep.py      downscale, EXIF rotate, guard       -> Ayush Rai
      ocr.py            bill photo -> text lines            -> Ayush Rai
      extract.py        text line -> structured item        -> Ayush Rai
      rules.py          regex/keyword fallback extractor    -> Ayush Rai
      pipeline.py       scan + confirm orchestration        -> Ayush Rai

      main.py           FastAPI app, router includes        -> Saket
      config.py         env vars, logging helper            -> Saket
      routes/
        scan.py         POST /api/scan, /api/scan/confirm   -> Saket
        chat.py         POST /api/chat (typed text)         -> Saket
        inventory.py    GET  /api/inventory                 -> Saket

      db.py             schema + connection                 -> Lokesh
      seed.py           demo shop, SKUs, aliases, history   -> Lokesh
      units.py          unit vocab (3 langs) + conversion   -> Lokesh
      inventory.py      movements, SKU creation, levels     -> Lokesh
      reorder.py        days of cover                       -> Lokesh
      resolver.py       alias / fuzzy / near-tie / learn     -> Lokesh
      reply.py          reply text in en / hi / kn          -> Lokesh

  frontend/
    index.html  app.js  styles.css        scan + review UI  -> Saket
    dashboard.html  dashboard.js                            -> Saket

  tests/
    corpus.md         bill + text test cases                -> Ayush Aditya
    bills/            sample bill photos                    -> Ayush Aditya

  docs/api-contract.md    frozen, do not change unilaterally
  README.md  TASKS.md  PROGRESS.md  LICENSE  .env.example
```

---

## The flow

```
  1. photo        2. downscale    3. vision        4. extract      5. resolve
     in browser      1024px          -> text          -> items        -> sku_id
                     EXIF fix        lines            per line        or candidates
                                                                          |
  7. ledger  <--  6. CONFIRM  <-----------------------------------------  |
     atomic         shopkeeper reviews, fixes, approves
     write          nothing written before this point
```

Steps 1–5 have **no side effects**. Step 6 is the only thing that writes. Abandoning a scan
costs nothing.

---

## Module contracts

These signatures are the agreement. Build against them with stubs.

### `llm.py` — Saket

```python
def generate(prompt: str, schema: dict | None = None,
             images: list[bytes] | None = None,
             timeout: float = 40.0) -> dict | str
```

One entry point to Ollama. POSTs `/api/generate` with `stream: false`,
`options: {"temperature": 0, "num_ctx": 4096}`, `think: false`, `keep_alive: "30m"`.
Returns parsed JSON when `schema` is given, else the raw string. Raises on failure.

Vision timeout is higher than text — a bill photo takes longer than a sentence.

### `imageprep.py` — Saket

```python
def prepare(raw: bytes, max_edge: int = 1024) -> bytes
```

EXIF-rotate (phone photos are frequently sideways, and a sideways bill reads terribly),
downscale so the longest edge is `max_edge`, convert to JPEG, strip metadata. Raise on
anything that isn't a decodable image.

**This function is the difference between a 4-second scan and a 40-second one.** Write it
before `ocr.py`.

### `ocr.py` — Saket

```python
def read_bill(image: bytes) -> dict
```

Returns:

```python
{
  "lines": ["20 packet parle-g 480", "2 dozen maggi 240", ...],
  "raw_text": "...",          # the full transcription, for display
  "script": "latin" | "devanagari" | "kannada" | "mixed",
  "legible": True,            # False when the model says it can't read it
  "confidence": "high" | "low",
}
```

Prompt requirements:

- **One item per line.** `<qty> <unit> <item name> <price if present>`.
- **Transliterate to Latin script**, whatever the bill is written in.
- Prices as plain numbers, no currency symbols.
- **If the image isn't a bill, or is illegible, say so** — set `legible: false` rather than
  inventing line items. A hallucinated delivery is the worst possible output here.
- Handwritten bills: instruct it to skip lines it cannot read rather than guess, and report
  `confidence: "low"` so the UI can warn the shopkeeper to check carefully.

### `extract.py` — Saket

```python
def extract_line(line: str) -> dict          # one bill line -> one item
def extract_message(text: str) -> dict       # a typed sentence -> intent + items
```

`extract_line` returns `{"name", "qty", "unit", "price_paise", "_source"}`.

`extract_message` returns `{"intent", "lang", "items", "_source"}` for the typed-text path.

Hard requirements for both:

- `unit` constrained by **enum** to exactly what `units.py` understands. Without the enum the
  model invents units like `"units"` and every downstream step degrades silently.
- `name` in **Latin script, lowercase**.
- `_source` is `"llm"` or `"rule"`, surfaced in the API response so a silent fallback is
  visible rather than buried in a log.
- On any failure, fall through to `rules.py`. Never raise to the caller.

### `rules.py` — Saket

```python
def extract_line(line: str) -> dict
def extract_message(text: str) -> dict
```

For bill lines this is mostly a regex: a leading number, a unit word, the rest as the name,
a trailing number as price. That handles a surprising share of printed bills and costs
nothing. English + Hindi vocabulary only — Kannada has no rule path, and that's a disclosed
limitation.

### `db.py` / `seed.py` — Lokesh

| Table | Columns that matter |
|---|---|
| `shops` | `id`, `name` |
| `skus` | `id`, `shop_id`, `name`, `canonical_unit`, `current_qty`, `cost_per_unit`, `sell_price` |
| `aliases` | `id`, `shop_id`, `text` (Latin, lowercase), `sku_id` |
| `stock_ledger` | `id`, `sku_id`, `direction`, `qty`, `unit_as_said`, `price_paise`, `ts`, `scan_id` |
| `scans` | `id`, `shop_id`, `raw_text`, `items_json`, `status`, `ts` |
| `messages` | `id`, `sender`, `direction`, `body`, `ts` |

- **Money is integer paise.** Float rupees produce wrong totals.
- `scans` holds a pending scan between the scan call and the confirm call. `status` is
  `pending` / `confirmed` / `abandoned`.
- `stock_ledger.scan_id` ties a movement back to the bill it came from — that's the audit
  trail, and it's a good thing to show a judge.
- `seed.py` creates ~30 real kirana SKUs, a starting alias list, and **14 days of sales
  history**. The history isn't optional; days-of-cover and the low-stock alert show nothing
  without it. Add `--reset`.

### `units.py` — Lokesh

```python
UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"]

def normalize_unit(word: str, lang: str = "en") -> str | None
def convert(qty: float, from_unit: str, sku_id: int) -> tuple[float, bool]
```

`normalize_unit` returns `None` for anything unrecognised — **never pass unknown words
through**, or they get stored as a SKU's canonical unit forever.

`convert` returns `(qty_in_canonical_unit, confident)`. Conversions are **per-SKU**: a box of
Coke is 24, a box of something else isn't.

Known collisions: bare `g` must **not** map to grams (it eats `parle g`); `pav` stays a unit
and is removed from any bread alias.

Bills add their own: `pkt`, `pc`, `nos`, `bdl`, `jar`, `tin` are common printed-bill
abbreviations. Add them.

### `resolver.py` — Lokesh

```python
def resolve(shop_id: int, name: str) -> dict
def learn_alias(shop_id: int, text: str, sku_id: int) -> None
```

`resolve` returns:

```python
{"status": "exact" | "fuzzy" | "ambiguous" | "unknown",
 "sku_id": int | None,
 "candidates": [{"sku_id": int, "name": str, "score": int}]}
```

Four behaviours in order:

1. Exact alias hit → `exact`
2. Top fuzzy above threshold **and** clearly ahead of second → `fuzzy`
3. **Near-tie** — top two within ~5 points → `ambiguous`, **regardless of how high the top
   score is.** `amul` scores ~90 against both Amul Butter and Amul Milk; taking the top is
   right half the time and silently wrong the rest.
4. Nothing close → `unknown`, offer to create

`learn_alias` is called **only from the confirm step**, when a human actually picked the SKU.
A `fuzzy` auto-accept must **never** write an alias — nobody confirmed it, and cementing an
unconfirmed guess is how one slightly-off match becomes permanently wrong. The agent may be
temporarily wrong; it must not make itself permanently wrong.

This is the highest-scoring file in the repo. It's also fully testable with fixtures, **with
no model running.**

### `inventory.py` — Lokesh

```python
def apply_movement(shop_id, sku_id, direction, qty_canonical,
                   price_paise=None, unit_as_said=None, scan_id=None) -> None
def apply_scan(shop_id, scan_id, confirmed_items) -> list[dict]
def create_sku(shop_id, name, unit) -> int
def levels(shop_id) -> list[dict]
```

- **`apply_scan` is one transaction.** A bill is all-or-nothing: ten rows must not half-commit
  if row seven fails. One connection, one commit, rollback on any error.
- Stated price converts **by the same ratio as the quantity**. A rate per box on a 24-per-box
  SKU isn't the per-packet cost.
- Direction picks the column: `cost_per_unit` on `stock_in`, `sell_price` on `stock_out`.
  A supplier bill is always `stock_in`.
- `current_qty` **floors at 0**; the ledger still records the full reported movement.
- `create_sku` validates `unit` against `units.UNITS`, falls back to `"packet"`.

### `reply.py` — Lokesh

```python
def scan_summary(items: list[dict], lang: str) -> str
def confirm_summary(actions: list[dict], lang: str) -> str
def illegible(lang: str) -> str
```

Short, friendly, in the shopkeeper's language. `illegible` is the honest "couldn't read that"
for a non-bill or unreadable photo.

### `pipeline.py` — Ayush Rai

```python
def scan_bill(shop_id: int, image: bytes) -> dict
def confirm_scan(shop_id: int, scan_id: int, decisions: list[dict]) -> dict
def handle_message(shop_id: int, sender: str, text: str) -> dict
```

**`scan_bill`** — read-only:

1. `imageprep.prepare()`
2. `ocr.read_bill()` → if `legible` is false, return early with `reply.illegible()`. **Do not
   proceed to extraction on an unreadable image.**
3. For each line: `extract.extract_line()`
4. For each item: `units.normalize_unit()` → unknown unit is **not** an error here, it's a
   flag on that row for the shopkeeper to fix
5. For each item: `resolver.resolve()` → attach status and candidates
6. Persist to `scans` with `status: "pending"`, return the review payload

**`confirm_scan`** — the only thing that writes:

1. Load the pending scan; reject if already confirmed (idempotency — a double-tap on Confirm
   must not book the bill twice)
2. For each decision: `book` → apply; `skip` → ignore; `new` → `create_sku` then apply
3. Where the shopkeeper picked a SKU for an unresolved line → `resolver.learn_alias()`
4. `inventory.apply_scan()` in one transaction
5. Mark the scan `confirmed`, return the actions

Wrap both in `starlette.concurrency.run_in_threadpool` from the route — sync SQLite plus a
blocking HTTP call inline in an async route stalls every other request.

---

## Build order

```
llm.py -> imageprep.py -> ocr.py -> extract.py -> rules.py -> pipeline.py  (Ayush Rai)
db.py -> seed.py -> units.py -> inventory.py -> resolver.py -> reply.py    (Lokesh)
main.py -> stub routes -> frontend -> review table                        (Saket)
bills -> the gate -> corpus -> integration host -> QA -> demo             (Ayush Aditya)
```

`resolver.py` needs no model. The frontend needs no backend. Stubs exist from T+0:30.
Ayush Rai's `ocr.py` is the only thing blocked on anything — it needs bill photos, which is
why those are Ayush Aditya's first task at T+0:00.

---

## T+0:00 gate — before anything else

Four tests on the 4060, twenty minutes. **Ayush Aditya runs them** — it's his machine, so he
has the fastest iteration loop. Results go in `PROGRESS.md`.

1. **Printed bill.** A clean printed bill photo, downscaled to 1024 px. Does it come back as
   usable one-item-per-line text?
2. **Handwritten bill.** Same, handwritten. How bad is it? This is the headline risk.
3. **Latency.** A full scan end to end. Under ~8 s is acceptable for a photo; over ~15 s and
   the demo drags.
4. **Non-bill guard.** Send a photo of something else. Does it say so, or hallucinate items?

**Test 4 matters as much as test 1.** A model that invents a delivery from a photo of a wall
is worse than one that reads nothing.

If handwritten fails: demo printed bills, and say plainly that handwritten is next. That's an
honest limitation, not a hole.

---

## Cut list, in order

Agreed now so falling behind is a decision already made rather than an argument.

| # | Cut | Why it's safe |
|---|---|---|
| 1 | **Voice input** | Was the old core; now a bonus. Vision needs the VRAM and the dev time more. |
| 2 | **Handwritten bills** | Demo printed only. Keep the code path, disclose the limitation. |
| 3 | **Kannada** | Riskiest language, only one with no rule fallback |
| 4 | Proactive reorder nudge | The dashboard already shows low stock in red |
| 5 | Dashboard | The scan → review → confirm flow alone carries the demo |

**Never cut:** `ocr.py`, `resolver.py`, the **confirm step**, or the seeded history. Those
four are the project.
