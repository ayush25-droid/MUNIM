# Progress

**Everyone: update this as you finish things.** Some of us are using AI agents that will run
out of context. When a new session starts, this file is the handoff.

Tick your boxes, and append **one line** to the log at the bottom with the time. Facts, not
prose — the next reader needs what's true now, not a narrative.

---

## Status at a glance

| | Current task | Blocked on | Last pushed |
|---|---|---|---|
| **Ayush Rai** — the spine | `llm.py` | nothing (bills ready in `tests/bills/`) | — |
| **Saket** — API + review UI | waiting on `pipeline.py` to swap stubs | `pipeline.py` (Ayush Rai) | 90ed477 |
| **Lokesh** — data + resolver | `db.py` | nothing | — |
| **Ayush Aditya** — machine, bills, QA | integration & demo prep | nothing | T+0:20 |

**Overall: Gate tests PASSED. All bills unblocked.**

The 4060 is **Ayush Aditya's laptop** (`http://172.1.58.57:11434`). The model lives there,
integration happens there, the demo runs from there.

---

## The gate — fill this in first

**Ayush Aditya** answers these before anything else gets built — it's his machine, so he has
the fastest iteration loop. They decide what ships.

| Test | Result | Decision |
|---|---|---|
| **Printed** bill → usable one-item-per-line text? | PASS: 100% extracted lines, clean quantities and prices | proceed with full printed pipeline |
| **Handwritten** bill → how bad? | PASS: exceptional (7.67s, all 5 items parsed cleanly with shorthand) | full support, demo both printed + handwritten |
| Item names returned in **Latin script**? | PASS: English, shorthand, and Kannada all transliterated to Latin | Latin-only single-alias architecture confirmed |
| Full scan latency | PASS: 7.67s handwritten, ~11-17s distorted, cold load ~70s (warm stays under 15s) | enforce keep_alive 30m, 1024px limit |
| **Non-bill photo** → refused, or hallucinated items? | PASS: zero items invented (`legible: false`, `lines: []`, 4.7s) | prompt guard solid, no hallucinations |
| Kannada bill → readable? | PASS: numerals, prices, and lines transliterated; vernacular OCR handles names | retain Kannada with human confirm |

---

## Checklist

### Shared — T+0:00 → T+0:20
- [x] `docs/api-contract.md` read out loud together and frozen
- [x] All four can describe the scan/confirm split
- [x] Everyone can reach `http://172.1.58.57:11434/api/tags`
- [x] `OLLAMA_MAX_LOADED_MODELS=1` set on the 4060
- [x] `ollama list` confirms `gemma4:latest`
- [x] **Two bill photos in `tests/bills/`** (printed + handwritten) — unblocks Saket
- [x] Cut list agreed out loud

### Ayush Rai — the spine
- [ ] `llm.py` — `generate()`, `think: false`, `num_ctx: 4096`, `keep_alive: "30m"`
- [ ] `llm.py` — longer timeout for image calls than text
- [ ] `imageprep.py` — **EXIF rotate + downscale to 1024 px** (write this before `ocr.py`)
- [ ] `ocr.py` — one item per line, transliterated to Latin, prices as plain numbers
- [ ] `ocr.py` — **`legible: false` instead of inventing items** on a non-bill
- [ ] `ocr.py` — skips unreadable handwritten lines rather than guessing; reports `confidence`
- [ ] `extract.py` — `extract_line()`, pinned schema with unit **enum**
- [ ] `extract.py` — `extract_message()` for the typed-text path
- [ ] `rules.py` — regex fallback for bill lines, wired as `extract`'s except path
- [ ] `pipeline.py` — `scan_bill` read-only
- [ ] `pipeline.py` — `confirm_scan` idempotent, **409 on a repeat**
- [ ] `pipeline.py` — `run_in_threadpool` from the route
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

### Saket — API + review UI
- [x] `main.py`, `config.py`
- [x] Stub routes returning contract fixtures — including `legible: false` — **pushed early**
- [x] `index.html` — camera/upload as the **primary action**, works at phone width
- [x] **Client-side downscale to 1024 px before upload**
- [x] **Review table** — row per line, dropdown for `ambiguous`, create for `unknown`, unit
      picker where `unit_ok` is false, editable qty/price, skip toggle
- [x] `raw_text` displayed alongside the table
- [x] `legible: false` handled; `confidence: "low"` shows the check-carefully banner
- [x] Confirm POST; `aliases_learned` shown in the result
- [x] `escapeHtml` on everything from the API (OCR text especially)
- [x] In-flight guard on Confirm — a double tap must be a no-op
- [x] `dashboard.html` — low rows red *(cut if behind)*
- [ ] Stubs swapped for Ayush Rai's real pipeline

### Ayush Aditya — the machine, bills, QA, delivery
- [x] `OLLAMA_MAX_LOADED_MODELS=1` set, `ollama list` confirms `gemma4:latest`
- [x] **The gate run, results posted above**
- [x] Ollama reachable from all three other machines throughout
- [ ] **Full stack running on this laptop by T+1:30** (clone, backend, seed, frontend)
- [x] **Printed bill photo** in `tests/bills/`
- [x] **Handwritten bill photo** in `tests/bills/`
- [x] Bad angle, glare, crumpled
- [x] **A photo that isn't a bill at all** (hallucination guard)
- [x] Kannada-script bill
- [x] `tests/corpus.md` — expected items for every bill
- [x] Kannada unit vocabulary verified, corrections to Lokesh
- [x] `README.md` current — what it does, how to run, model + dependencies
- [x] Demo script written (`docs/demo-script.md`)
- [ ] "Before" dashboard screenshot while stock is low
- [ ] Four demo screenshots
- [ ] Backup recording
- [x] Slides; every member briefed on their own area (`docs/slides.md`)

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
| Windows console default cp1252 charmap crashes when printing Kannada/Hindi text | Use `ensure_ascii=True` or set UTF-8 stream output |
| Cold-start Ollama vision load takes ~70s on first inference | Keep `keep_alive: 30m` so model stays resident in GPU memory; warm calls take 7-12s |

---

## Log

Format: `HH:MM — who — what`

```
14:15 — Saket — backend skeleton (main/config/routes, stubs) + full frontend (scan, review table, dashboard) done; browser-tested against stubs
14:20 — Ayush Aditya — Environment verified (RTX 4060, Ollama gemma4:latest, OLLAMA_MAX_LOADED_MODELS=1). Full test bills suite generated in tests/bills/. Gate tests run and passed: printed 100%, handwritten 5/5 shorthand lines parsed in 7.67s, not-a-bill refused cleanly without hallucination, Kannada transliterated. Teammates unblocked.
```
