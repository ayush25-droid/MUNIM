# Progress

**Everyone: update this as you finish things.** Some of us are using AI agents that will run
out of context. When a new session starts, this file is the handoff.

Tick your boxes, and append **one line** to the log at the bottom with the time. Facts, not
prose — the next reader needs what's true now, not a narrative.

---

## Status at a glance

| | Current task | Blocked on | Last pushed |
|---|---|---|---|
| **Saket** — vision + extraction | the T+0:20 gate | **bill photos from Ayush Aditya** | — |
| **Lokesh** — data + resolver | `db.py` | nothing | — |
| **Ayush Rai** — API + review UI | stub routes | nothing | — |
| **Ayush Aditya** — bills + delivery | photographing bills | nothing | — |

**Overall: T+0:00. Nothing built yet.**

---

## The gate — fill this in first

Saket answers these before anything else gets built. They decide what ships.

| Test | Result | Decision |
|---|---|---|
| **Printed** bill → usable one-item-per-line text? | — | if no → the project needs rethinking, escalate immediately |
| **Handwritten** bill → how bad? | — | if bad → demo printed only, disclose it |
| Item names returned in **Latin script**? | — | if no → the multilingual strategy needs rethinking |
| Full scan latency | — | over ~15 s → check image size, `think`, `num_ctx`, cold load |
| **Non-bill photo** → refused, or hallucinated items? | — | if hallucinated → tighten the prompt, this is a demo-killer |
| Kannada bill → readable? | — | if no → Kannada is cut |

---

## Checklist

### Shared — T+0:00 → T+0:20
- [ ] `docs/api-contract.md` read out loud together and frozen
- [ ] All four can describe the scan/confirm split
- [ ] Everyone can reach `http://172.1.58.57:11434/api/tags`
- [ ] `OLLAMA_MAX_LOADED_MODELS=1` set on the 4060
- [ ] `ollama list` confirms `gemma4:latest`
- [ ] **Two bill photos in `tests/bills/`** (printed + handwritten) — unblocks Saket
- [ ] Cut list agreed out loud

### Saket — vision + extraction
- [ ] The gate, results posted above
- [ ] `llm.py` — `generate()`, `think: false`, `num_ctx: 4096`, `keep_alive: "30m"`
- [ ] `llm.py` — longer timeout for image calls than text
- [ ] `imageprep.py` — **EXIF rotate + downscale to 1024 px** (write this before `ocr.py`)
- [ ] `ocr.py` — one item per line, transliterated to Latin, prices as plain numbers
- [ ] `ocr.py` — **`legible: false` instead of inventing items** on a non-bill
- [ ] `ocr.py` — skips unreadable handwritten lines rather than guessing; reports `confidence`
- [ ] `extract.py` — `extract_line()`, pinned schema with unit **enum**
- [ ] `extract.py` — `extract_message()` for the typed-text path
- [ ] `rules.py` — regex fallback for bill lines, wired as `extract`'s except path
- [ ] Every bill in `tests/bills/` passing

### Lokesh — data + resolver
- [ ] `db.py` — six tables including `scans`, money in integer paise
- [ ] `seed.py` — ~30 SKUs + starting aliases
- [ ] `seed.py` — **14 days of sales history**
- [ ] `seed.py --reset`
- [ ] `units.py` — three-language vocabulary
- [ ] `units.py` — **printed-bill abbreviations** (`pkt`, `pc`, `nos`, `dzn`, `bdl`, `jar`, `tin`)
- [ ] `units.py` — bare `g` is not grams; `normalize_unit` returns `None` on unknown
- [ ] `inventory.py` — `apply_movement`, one connection one commit
- [ ] `inventory.py` — **`apply_scan` as one transaction** (a bill is all-or-nothing)
- [ ] `inventory.py` — price converts by the same ratio as qty; `current_qty` floors at 0
- [ ] `resolver.py` — exact alias
- [ ] `resolver.py` — fuzzy
- [ ] `resolver.py` — **near-tie → ambiguous**
- [ ] `resolver.py` — `learn_alias` only from the confirm step
- [ ] `reorder.py` — days of cover
- [ ] `reply.py` — `scan_summary`, `confirm_summary`, `illegible`, three languages

### Ayush Rai — API + review UI
- [ ] `main.py`, `config.py`
- [ ] Stub routes returning contract fixtures — including `legible: false` — **pushed early**
- [ ] `index.html` — camera/upload as the **primary action**, works at phone width
- [ ] **Client-side downscale to 1024 px before upload**
- [ ] **Review table** — row per line, dropdown for `ambiguous`, create for `unknown`, unit
      picker where `unit_ok` is false, editable qty/price, skip toggle
- [ ] `raw_text` displayed alongside the table
- [ ] `legible: false` handled; `confidence: "low"` shows the check-carefully banner
- [ ] Confirm POST; `aliases_learned` shown in the result
- [ ] `escapeHtml` on everything from the API (OCR text especially)
- [ ] `pipeline.py` — `scan_bill` read-only
- [ ] `pipeline.py` — `confirm_scan` idempotent, **409 on a repeat**
- [ ] `pipeline.py` — `run_in_threadpool` from the route
- [ ] `dashboard.html` — low rows red *(cut if behind)*
- [ ] Stubs swapped for the real pipeline

### Ayush Aditya — bills + delivery
- [ ] **Printed bill photo** in `tests/bills/`
- [ ] **Handwritten bill photo** in `tests/bills/`
- [ ] Bad angle, glare, crumpled
- [ ] **A photo that isn't a bill at all** (hallucination guard)
- [ ] Kannada-script bill
- [ ] `tests/corpus.md` — expected items for every bill
- [ ] Kannada unit vocabulary verified, corrections to Lokesh
- [ ] `README.md` current — what it does, how to run, model + dependencies
- [ ] Demo script written
- [ ] "Before" dashboard screenshot while stock is low
- [ ] Four demo screenshots
- [ ] Backup recording
- [ ] Slides; every member briefed on their own area

### Endgame — everyone, T+2:50
- [ ] Every bill in `tests/bills/` scanned end to end
- [ ] Ask-once verified: ambiguous line → pick → confirm → **re-scan the same bill** → silent
- [ ] Non-bill photo correctly refused
- [ ] Double-tap Confirm → 409, not a double booking
- [ ] `seed.py --reset` then final screenshots
- [ ] Everything pushed

---

## Decisions made — don't relitigate

| Decision | Reason |
|---|---|
| **Bill OCR is the core feature; voice is cut** | The bill is already in the shopkeeper's hand at the moment stock changes. One photo beats a spoken list. |
| **No WhatsApp — it's a web app** | Twilio trials block outbound replies and eat hours. The web UI screenshots identically. |
| **Scan is read-only; confirm is the only writer** | A bill writes many rows at once and handwritten OCR is imperfect. Committing ten unreviewed rows is the exact failure this design exists to prevent. |
| Vision flattens to text, then the normal pipeline runs | Keeps the rule fallback usable, one code path to debug, and the transcript is showable so the shopkeeper can correct a misread line |
| One model (`gemma4:latest`) for vision and text | 6.9 GB usable VRAM won't hold two. Also less to integrate. |
| **Downscale every image to 1024 px** | A full-res phone photo encodes to thousands of image tokens — blows the context window and makes inference crawl |
| `num_ctx` stays 4096 | Model advertises 131072; requesting it OOMs instantly |
| `think: false` | Extended reasoning costs seconds we don't have; this is extraction, not reasoning |
| Near-tie rule in the resolver | `amul` scores ~90 against both Butter and Milk; picking the top silently books the wrong item |
| Fuzzy auto-accept never writes an alias | Nobody confirmed it. Temporarily wrong is fine; permanently wrong is not. |
| Transliterate during OCR | Keeps the resolver and alias table script-agnostic. One alias row serves three languages. |
| Money as integer paise | Float rupees produce wrong totals |
| SQLite, not Postgres | No service to provision |
| `rapidfuzz`, not embeddings | Good enough for kirana names, zero setup |
| Plain HTML, no React | No build step to break at hour two |
| No barcode scanning | Most kirana stock isn't barcoded — which is the point of reading the bill instead |
| No auth / multi-tenant | One hardcoded demo shop |

---

## Known issues / gotchas hit

_Append as you hit them. Saves the next person an hour._

| Issue | Workaround |
|---|---|
| | |

---

## Log

Format: `HH:MM — who — what`

```
```
