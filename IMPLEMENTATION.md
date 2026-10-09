# Implementation Guide

Read this before writing a line. It defines the architecture, the hard hardware limit, and
the exact contract between every module so four people can build in parallel without
waiting on each other.

---

## The one decision everything follows from

**One model does everything.** `gemma4:latest` on the 4060 reports
`["completion", "vision", "audio", "tools", "thinking"]`. That replaces the three-model
stack we planned:

| Originally planned | Now |
|---|---|
| Whisper for speech → text | Gemma 4 audio input |
| A separate LLM for extraction | Gemma 4 with schema-constrained output |
| A separate vision model for bill photos | Gemma 4 vision |

One model loaded, three capabilities, and we stay inside VRAM. If the audio path turns out
to be unusable (see **T+0:00 gate** below) we fall back to typed text and lose only the
voice demo, not the project.

---

## Hardware limit — read this, it is the binding constraint

The inference box is **one** machine: the RTX 4060 laptop at `http://172.1.58.57:11434`.

```
Total VRAM                      8.0 GiB
Available (reported by Ollama)  6.9 GiB
gemma4:latest  Q4_K_M weights  ~6.1 GiB
KV cache @ num_ctx 4096        ~0.3-0.5 GiB
                               ----------
                               ~6.5 GiB   leaves ~400 MiB
```

**Four rules. Breaking any one of them OOMs the demo.**

1. **Never load a second model.** Set `OLLAMA_MAX_LOADED_MODELS=1` on the server. Do not
   pull a "quick comparison" model and leave it resident.
2. **Keep `num_ctx` at 4096.** The model advertises 131072. Requesting anything close to
   that allocates a KV cache many times larger than the free VRAM and will fail instantly.
   4096 is far more than our messages need.
3. **Disable `thinking`.** Extended reasoning costs seconds we do not have for an
   interactive demo, and we are doing constrained extraction, not reasoning.
4. **Set `keep_alive` long** (e.g. `"30m"`) so the model is not unloaded and reloaded
   between requests. A cold load is ~20-40 s and will look like a hang during judging.

**If it OOMs anyway:** drop `num_ctx` to 2048 first. Audio and vision inputs need extra
working memory beyond the figures above, so test those specifically rather than assuming
headroom.

---

## Stack

| Layer | Choice | Why |
|---|---|---|
| Inference | Ollama on the 4060, `gemma4:latest` | Already installed, already pulled, no download risk |
| Backend | Python 3.11+, FastAPI | Fast to write, async where it matters |
| Database | SQLite | No service to run, nothing to provision |
| Matching | `rapidfuzz` | Deterministic, fast. `difflib.SequenceMatcher` if pip fails |
| Frontend | Plain HTML + CSS + vanilla JS | No build step, no CDN that dies with venue wifi |

Everything runs on the 4060 laptop for the demo. The other three develop locally against
the same Ollama endpoint over the LAN.

---

## File tree and ownership

Nobody edits a file they do not own. This is what keeps four people out of each other's way.

```
MUNIM/
  backend/
    requirements.txt
    app/
      __init__.py
      main.py           FastAPI app, router includes        -> Ayush Rai
      config.py         env vars, logging helper            -> Ayush Rai
      pipeline.py       orchestration + pending state       -> Ayush Rai
      routes/
        chat.py         POST /api/chat                      -> Ayush Rai
        inventory.py    GET  /api/inventory                 -> Ayush Rai

      llm.py            Ollama adapter                      -> Saket
      extract.py        schema-constrained extraction       -> Saket
      rules.py          keyword fallback extractor          -> Saket
      reply.py          reply text in en / hi / kn          -> Saket

      db.py             schema + connection                 -> Lokesh
      seed.py           demo shop, SKUs, aliases, history   -> Lokesh
      units.py          unit vocab (3 langs) + conversion   -> Lokesh
      inventory.py      movements, SKU creation, levels     -> Lokesh
      reorder.py        days of cover                       -> Lokesh
      resolver.py       alias / fuzzy / near-tie / learn     -> Lokesh

  frontend/
    index.html  app.js  styles.css                          -> Ayush Rai
    dashboard.html  dashboard.js                            -> Ayush Rai

  tests/
    corpus.md         test sentences, all 3 languages       -> Ayush Aditya

  docs/api-contract.md    frozen, do not change unilaterally
  README.md  TASKS.md  PROGRESS.md  LICENSE  .env.example
```

---

## Module contracts

These signatures are the agreement. Build against them with stubs; they will still fit when
the real thing lands.

### `llm.py` — Saket

```python
def generate(prompt: str, schema: dict | None = None,
             images: list[bytes] | None = None,
             audio: bytes | None = None,
             timeout: float = 25.0) -> dict | str
```

Single entry point to Ollama. POSTs to `/api/generate` with `stream: false`,
`options: {"temperature": 0, "num_ctx": 4096}`, `think: false`, `keep_alive: "30m"`.
Returns parsed JSON when `schema` is given, else the raw string. Raises on timeout or
transport failure — callers decide what to do.

### `extract.py` — Saket

```python
def extract(text: str | None = None,
            audio: bytes | None = None,
            image: bytes | None = None,
            catalog_hint: list[str] | None = None) -> dict
```

Returns:

```python
{
  "intent": "stock_in" | "stock_out" | "query" | "unknown",
  "lang":   "en" | "hi" | "kn",
  "items":  [{"name": str, "qty": float, "unit": str, "price_paise": int | None}],
  "_source": "llm" | "rule",
}
```

Hard requirements:

- `unit` is constrained by **enum** to exactly what `units.py` understands. Without the
  enum the model invents units like `"units"` and every downstream step silently degrades.
- `name` must come back in **Latin script, lowercase**, transliterated from Kannada or
  Devanagari. This is what lets one alias table serve all three languages.
- A `query` intent must return an **empty** `items` list. A question must never move stock.
- On any failure — timeout, bad JSON, transport error — fall through to `rules.extract()`
  and tag `_source: "rule"`. Never raise to the caller.

### `rules.py` — Saket

```python
def extract(text: str) -> dict   # same shape, "_source": "rule"
```

Keyword fallback. Vocabulary is **English and Hindi only** — Kannada has no rule path, and
that is a disclosed limitation, not an oversight. Stock-in verbs: `aaye`, `aaya`, `came`,
`received`. Stock-out requires an explicit sale verb (`bik`, `bech`, `nikla`, `sold`) —
never the bare auxiliary `gaya`/`gaye`, because "rate badh gaya" is a price change, not a
sale. Returns `intent: "unknown"` rather than guessing.

### `reply.py` — Saket

```python
def confirm(actions: list[dict], lang: str) -> str
def ask_sku(name: str, candidates: list[dict], lang: str) -> tuple[str, list[dict]]
def ask_unit(name: str, unit_word: str, lang: str) -> tuple[str, list[dict]]
def not_understood(lang: str) -> str
```

The `ask_*` functions return `(text, options)`. Each option is
`{"label": "Amul Butter", "value": "sku:7"}`. **Spell the choices out in the text too** —
a WhatsApp user has no buttons and will type the answer in words.

### `db.py` / `seed.py` — Lokesh

Six tables:

| Table | Columns that matter |
|---|---|
| `shops` | `id`, `name` |
| `skus` | `id`, `shop_id`, `name`, `canonical_unit`, `current_qty`, `cost_per_unit`, `sell_price` |
| `aliases` | `id`, `shop_id`, `text` (Latin, lowercase), `sku_id` |
| `stock_ledger` | `id`, `sku_id`, `direction`, `qty`, `unit_as_said`, `price_paise`, `ts` |
| `pending_questions` | `sender`, `payload` (JSON), `ts` |
| `messages` | `id`, `sender`, `direction`, `body`, `ts` |

- **Money is integer paise.** Float rupees produce wrong totals.
- `seed.py` creates ~30 real kirana SKUs, a starting alias list, and **14 days of sales
  history**. The history is not optional — days-of-cover and the low-stock alert produce
  nothing without it, and it is always left too late.
- `seed.py --reset` wipes and reseeds. Run it before the final screenshots.

### `units.py` — Lokesh

```python
UNITS = ["packet", "box", "sack", "dozen", "kg", "gram", "litre", "piece"]

def normalize_unit(word: str, lang: str = "en") -> str | None
def convert(qty: float, from_unit: str, sku_id: int) -> tuple[float, bool]
```

`normalize_unit` returns `None` for anything unrecognised — **do not pass unknown words
through unchanged**, or they get stored as a SKU's canonical unit forever.

`convert` returns `(qty_in_canonical_unit, confident)`. Conversions are **per-SKU**, not
global: a box of Coke is 24, a box of something else is not.

Vocabulary table lives here, keyed by language. Two collisions already known:
bare `g` must **not** map to grams (it eats "parle g"); `pav` stays a unit and is removed
from any bread alias.

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

Four behaviours, in order:

1. Exact alias hit → `exact`.
2. Top fuzzy score above threshold **and** clearly ahead of second place → `fuzzy`.
3. **Near-tie** — top two within a narrow band (~5 points) → `ambiguous`, **regardless of
   how high the top score is.** `amul` scores ~90 against both Amul Butter and Amul Milk;
   taking the top one is right half the time and silently wrong the rest.
4. Nothing close → `unknown`, offer to create.

`learn_alias` is called **only** when a human answered a question or named a new item.
A `fuzzy` auto-accept must **never** write an alias — no human confirmed it, and cementing
an unconfirmed guess is how one slightly-off match becomes permanently wrong. The agent may
be temporarily wrong; it must not make itself permanently wrong.

### `inventory.py` — Lokesh

```python
def apply_movement(shop_id, sku_id, direction, qty_canonical,
                   price_paise=None, unit_as_said=None) -> None
def create_sku(shop_id, name, unit) -> int
def levels(shop_id) -> list[dict]
```

- **One connection, one commit.** Separate writes can leave the ledger and `current_qty`
  disagreeing after a crash.
- A stated price converts **by the same ratio as the quantity**. A rate quoted per box on a
  24-per-box SKU is not the per-packet cost.
- Direction decides the column: `cost_per_unit` on `stock_in`, `sell_price` on `stock_out`.
- `current_qty` **floors at 0**; the ledger still records the full reported movement. An
  audit trail should show what was said.
- `create_sku` validates `unit` against `units.UNITS` and falls back to `"packet"`.

### `pipeline.py` — Ayush Rai

```python
def handle_message(shop_id: int, sender: str, text: str | None = None,
                   audio: bytes | None = None, mime: str | None = None) -> dict
```

The orchestrator. Order matters:

1. If a `pending_questions` row exists for this sender, try to answer it **first**.
   **Clear the row before parsing the payload** — otherwise a malformed row crashes this
   sender on every future message, forever.
   If the message is not a valid answer, return `None` from the answer path and fall
   through to treating it as a brand-new message. Never swallow it.
2. `extract()`.
3. **Intent gate** — only `stock_in` / `stock_out` reach the resolver. A `query` goes to a
   real lookup; `unknown` gets `reply.not_understood()`.
4. For each item: resolve → on `ambiguous`/`unknown`, save a pending row carrying the
   **remaining items and the actions already booked**, and return the question. Answering
   resumes the rest, chaining through several questions in one message if needed.
5. Unit check before any write. Unrecognised unit → ask, write nothing.
6. `apply_movement`, then `reply.confirm()`.

Use one shared `_apply_item()` helper for both the main loop and the answer path. The unit
check living in only one of the two is exactly how that gap appears.

Wrap the whole call in `starlette.concurrency.run_in_threadpool` from the route — it is
sync SQLite plus a blocking HTTP call, and inline in an async route it stalls every other
request.

---

## Build order

Dependencies, so nobody blocks:

```
db.py -> seed.py -> units.py -> inventory.py -> resolver.py     (Lokesh, in sequence)
llm.py -> extract.py -> rules.py -> reply.py                    (Saket, in sequence)
main.py -> routes -> frontend -> pipeline.py                    (Ayush Rai)
corpus.md -> verification -> screenshots -> README              (Ayush Aditya)
```

`resolver.py` can be built and tested entirely with fixtures, **with no model running.**
`pipeline.py` is glue and comes last, once the pieces exist.

---

## T+0:00 gate — do this before anything else

Three tests on the 4060, fifteen minutes. They decide what we build.

1. **Text extraction, three languages.** Send an English, a Hindi and a Kannada sentence
   with the JSON schema. Check: right intent, right item count, units inside the enum,
   and **names returned in Latin script**. That last one is the whole multilingual strategy.
2. **Audio.** Send a real voice note. Usable transcript? If yes, Whisper is unnecessary.
   If no, voice is Hindi/English only, or typed text.
3. **Latency.** Under ~4 s per message end to end is fine. Slower means `thinking` is still
   on, or the model is cold-loading, or `num_ctx` is too high.

A Kannada speaker must judge test 1's Kannada output. Nobody else can tell a correct
transliteration from a plausible-looking wrong one — which is precisely the failure that
silently writes bad data.

---

## Cut list, in order

Agreed now so that falling behind is a decision already made rather than an argument.

| # | Cut | Why it is safe |
|---|---|---|
| 1 | Bill-photo vision | Same model, but extra working memory in a 400 MiB margin, and the voice path demonstrates the identical pipeline |
| 2 | Proactive reorder nudge | The dashboard already shows low stock in red |
| 3 | **Kannada** | Riskiest language, and the only one with no rule-based fallback |
| 4 | Voice input | Typed text still demonstrates the hard part — the resolver |
| 5 | Dashboard | The chat alone carries a screenshot |

**Never cut:** `extract.py`, `resolver.py`, or the seeded sales history. Those three are
the project.
