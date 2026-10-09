# Progress

**Everyone: update this as you finish things.** Some of us are using AI agents that will run
out of context. When a new session starts, this file is the handoff.

Tick your boxes, and append **one line** to the log at the bottom with the time. Facts, not
prose — the next reader needs what's true now, not a narrative.

---

## Status at a glance

| | Current task | Blocked on | Last pushed |
|---|---|---|---|
| **Ayush Rai** — the spine | spine done, verified against the live model, three bugs fixed. Also merged a voice-input prototype (`POST /api/voice`, en/hi/kn) into main | **Kannada voice not yet validated by a native speaker** — don't rely on it for the demo until someone checks | this push |
| **Saket** — API + review UI | done; verified live against the 4060 (printed/handwritten/Kannada/not-a-bill from the browser) | nothing | e5f188a |
| **Lokesh** — data + resolver | db/units/resolver/inventory/reorder/reply/seed done; two resolver bugs + a seed-data gap found against real data, all fixed below — Lokesh now on slides/PPT, so this is covered | nothing | this push |
| **Ayush Aditya** — machine, bills, QA | integration & demo prep | nothing — see `tests/corpus.md` for a found test-image bug in `generate_test_bills.py` (flagged, not fixed — not our file) | e91563d |

**Overall: full stack running and verified end-to-end on the live RTX 4060 (gemma4:latest), both
from the browser (Saket, Aditya) and by driving `pipeline.py` directly (Ayush Rai) — OCR ~2s, full
scan 4-8s warm. Ask-once (ambiguous → confirm → alias learned → silent re-scan) and 409 idempotency
both verified on live hardware by three independent runs. All six typed-text chat cases also run
against the live model for the first time — see `tests/corpus.md`'s second results table: 9/13
full-pipeline cases clean PASS, 3 PARTIAL (all traced to one corrupted test bill image, not the
pipeline — see Known Issues), 1 documented chat-surface limitation. Zero hallucinated items, zero
stock written from a query, anywhere. Three real bugs found by live testing (two by Saket, one by
Ayush Rai's own run) are fixed below. Ready for screenshots and demo.**

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
- [x] `llm.py` — `generate()`, `think: false`, `num_ctx: 4096`, `keep_alive: "30m"`
- [x] `llm.py` — longer timeout for image calls than text
- [x] `imageprep.py` — **EXIF rotate + downscale to 1024 px** (write this before `ocr.py`)
- [x] `ocr.py` — one item per line, transliterated to Latin, prices as plain numbers
- [x] `ocr.py` — **`legible: false` instead of inventing items** on a non-bill
- [x] `ocr.py` — skips unreadable handwritten lines rather than guessing; reports `confidence`
- [x] `extract.py` — `extract_line()`, pinned schema with unit **enum**
- [x] `extract.py` — `extract_message()` for the typed-text path
- [x] `rules.py` — regex fallback for bill lines, wired as `extract`'s except path
- [x] `pipeline.py` — `scan_bill` read-only
- [x] `pipeline.py` — `confirm_scan` idempotent, **409 on a repeat**
- [x] `pipeline.py` — `run_in_threadpool` from the route (already in `routes/scan.py`/`chat.py`)
- [x] Every bill in `tests/bills/` run against the live model via `pipeline.scan_bill`, plus all
      six typed-text chat cases via `handle_message` — see `tests/corpus.md`'s second results
      table. 4/7 bills clean, 3 PARTIAL (one corrupted test image, 3 of its 4 variants — not a
      pipeline bug, see Known Issues)

### Lokesh — data + resolver
**Built by Ayush Rai to unblock `pipeline.py` integration — Lokesh, please review against your
own judgment and adjust; nothing here is precious.** `db.py`'s CRUD function names and the
`unit_conversions` column on `skus` weren't frozen by any doc, so those are judgment calls made
during integration, documented in each file's module docstring.
- [x] `db.py` — six tables including `scans`, money in integer paise (plus a `unit_conversions`
      JSON column on `skus`, not in the original column list — needed for per-SKU packaging ratios)
- [x] `seed.py` — 30 SKUs + 38 starting aliases
- [x] `seed.py` — **14 days of sales history**
- [x] `seed.py --reset`
- [x] `units.py` — three-language vocabulary, including the Kannada corrections from
      `tests/corpus.md` (`moote` for sack, `nang`/`nangu`/`pees` for piece)
- [x] `units.py` — printed-bill abbreviations (`pkt`, `pc`, `nos`, `dzn`, `bdl`, `ctn`, `jar`, `tin`)
- [x] `units.py` — bare `g` is not grams; `normalize_unit` returns `None` on unknown
- [x] `inventory.py` — `apply_movement`, one connection one commit
- [x] `inventory.py` — **`apply_scan` as one transaction** (a bill is all-or-nothing)
- [x] `inventory.py` — price converts by the same ratio as qty; `current_qty` floors at 0
- [x] `resolver.py` — exact alias
- [x] `resolver.py` — fuzzy
- [x] `resolver.py` — **near-tie → ambiguous**
- [x] `resolver.py` — `learn_alias` only from the confirm step
- [x] `reorder.py` — days of cover
- [x] `reply.py` — `scan_summary`, `confirm_summary`, `illegible`, three languages (plus
      `stock_query_answer`, not in the original list — needed for `/api/chat`'s query intent to
      actually answer with a stock level, per the contract's own chat example)

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
- [x] Stubs swapped for Ayush Rai's real pipeline — automatic via `routes/errors.use_stubs()`
      now that `pipeline.py` exists; verified with `TestClient` against the live app, not fixtures.
      Fixed two bugs found doing that: `routes/scan.py` caught a misnamed exception
      (`ScanAlreadyConfirmed` vs. the real `ScanAlreadyConfirmedError`) and didn't handle
      `BadRequestError`/`ValidationError` at all; same missing `BadRequestError` handling in
      `routes/chat.py`. See "Known issues" below.

### Ayush Aditya — the machine, bills, QA, delivery
- [x] `OLLAMA_MAX_LOADED_MODELS=1` set, `ollama list` confirms `gemma4:latest`
- [x] **The gate run, results posted above**
- [x] Ollama reachable from all three other machines throughout
- [x] **Full stack running on this laptop by T+1:30** (clone, backend, seed, frontend)
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
- [x] Every bill in `tests/bills/` scanned end to end (tested on 4060: printed, handwritten, distorted, kannada, non-bill guard)
- [x] Ask-once verified: ambiguous line → pick → confirm → **re-scan the same bill** → silent (verified on live gemma4 model on 4060)
- [x] Non-bill photo correctly refused (verified on live gemma4 model on 4060)
- [x] Double-tap Confirm → 409, not a double booking (verified on live app on 4060)
- [ ] `seed.py --reset` then final screenshots
- [x] Everything pushed (this round)

---

## Decisions made — don't relitigate

| Decision | Reason |
|---|---|
| **Bill OCR is the core feature; voice is cut** *(revisited 16:35 — see log)* | The bill is already in the shopkeeper's hand at the moment stock changes. One photo beats a spoken list. Voice was added back as a secondary surface (`POST /api/voice`) alongside typed chat, not as a replacement for this — the original reasoning still holds for bills specifically. |
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
| `routes/scan.py` caught `pipeline.ScanAlreadyConfirmed` (wrong name) and no `pipeline.BadRequestError`/`ValidationError` at all -- a real double-confirm would've crashed with `AttributeError` instead of returning 409 | Fixed to catch `ScanAlreadyConfirmedError`/`ValidationError`/`BadRequestError` by their actual names; same gap existed in `routes/chat.py` for bad `shop_id`, fixed there too. Exception names/types aren't frozen anywhere in the docs -- `pipeline.py`'s module docstring is now the source of truth for them. |
| Seeded DB has no low-stock SKUs, so the dashboard shows no red rows (found by Saket) | **FIXED** — `seed.py`: lowered Maggi Noodles (5 packet) and Amul Milk (3 litre) starting qty against their sell-through; both now show `low: true` (0.7 and 1.3 days of cover) |
| `5 pc Amul Butter 500g` matches **exact** to "Amul Butter 100g" — the alias `amul butter` ignores size (found by Saket) | **FIXED** — `extract.py`'s prompt now keeps a size/weight suffix fused onto a word (`500g`, `1L`) as part of the extracted name instead of dropping it, so a differently-sized variant scores lower instead of matching exact. Took two follow-up prompt iterations to land without regressing other lines (see commit) — pure string-matching alone still can't fully distinguish sizes without a second SKU of the same product to compare against, so this reduces but doesn't eliminate the risk; a real second size variant in the catalog is the actual test. |
| Ambiguous dropdown for `aata` offered Tata Salt and Patanjali Ghee as candidates (found by Saket) | **FIXED** — `resolver.py` now only includes candidates within the near-tie margin of the top score, not a blind top-3; Ghee (68, outside the margin from Atta's 75) is excluded, Tata Salt (73, the actual near-tie partner) stays |
| Printed-bill line `140.00 Fortune Sunlite Refined Oil 1L12 pouch` parsed as qty 1 litre (found by Saket) | **Root cause found, not an extract.py bug** — see the `generate_test_bills.py` column-overlap row below. The "12 pouch" QTY-column text is drawn on top of "1L" from the item description in the source image; the model's output is a reasonable read of already-corrupted input, confirmed by `angle-01`/`glare-01`/`crumpled-01` reproducing the exact same garbling since they share the same source image |
| `tests/generate_test_bills.py`'s printed-bill layout: `QTY` column (x=450) collides with long `ITEM DESCRIPTION` text (starts x=60, no width cap) — `"Aashirvaad Shudh Chakki Atta 10kg"` and `"Tata Salt Vacuum Evaporated 1kg"` visually overlap their own QTY cells, illegible even to a human (found by Ayush Rai, tracing Saket's report above) | **For Ayush Aditya** — not our file. Widen the gap (move QTY to ~x=520+) or cap/wrap the description column, then regenerate `printed-01.jpg` (and the angle/glare/crumpled variants derived from it) |
| Phone cannot reach the app if backend binds to localhost or the laptop firewall (firewalld on Fedora) blocks 8000/5500 | Run uvicorn with `--host 0.0.0.0`, open both ports, browse with `?api=http://<laptop-ip>:8000` |
| `backend/requirements.txt` had two conflicting versions (unpinned + `requests`, vs. pinned + `httpx`) after independent pushes | Kept the pinned set; switched `llm.py` from `requests` to `httpx` rather than carrying two HTTP libraries |

---

## Log

Format: `HH:MM — who — what`

```
14:15 — Saket — backend skeleton (main/config/routes, stubs) + full frontend (scan, review table, dashboard) done; browser-tested against stubs
14:20 — Ayush Aditya — Environment verified (RTX 4060, Ollama gemma4:latest, OLLAMA_MAX_LOADED_MODELS=1). Full test bills suite generated in tests/bills/. Gate tests run and passed: printed 100%, handwritten 5/5 shorthand lines parsed in 7.67s, not-a-bill refused cleanly without hallucination, Kannada transliterated. Teammates unblocked.
14:45 — Ayush Rai — llm.py, imageprep.py, ocr.py, extract.py, rules.py, pipeline.py done. Also built Lokesh's db.py/units.py/resolver.py/inventory.py/reorder.py/reply.py/seed.py to unblock integration. Rebased onto Saket's + Aditya's pushes; fixed the ScanAlreadyConfirmed exception-name bug and missing BadRequestError/ValidationError handling in routes/scan.py + routes/chat.py. Added Kannada unit corrections (moote, nang/nangu, pees) from tests/corpus.md to units.py. Verified with TestClient against the real FastAPI app (not stubs): scan/confirm/chat/inventory, 400/409/422 error mapping, ambiguous near-tie -> confirm -> alias learned -> re-scan resolves silently. Not yet run against the live model on the 4060.
14:52 — Ayush Aditya — Pull completed; seed.py --reset run cleanly. Full stack live integration test executed against local Ollama gemma4:latest on the RTX 4060: handwritten-01.jpg scanned in 6.09s total (OCR 2.07s). Ambiguous near-tie (Maggi) prompted correctly, confirmed and booked, duplicate confirm rejected with 409 idempotency guard, and re-scan verified 100% exact resolution via learned aliases. Ask-once fully operational on hardware.
15:10 — Saket — Verified full stack against live Ollama on the 4060 (not stubs): printed/handwritten/Kannada/not-a-bill bills scanned from the browser in 6-8 s; ambiguous pick -> confirm (double-click = 1 POST) -> aliases learned -> re-scan resolves silently; non-bill refused; 409 on repeat confirm. Review table now stacks into cards below 640 px (no sideways scroll on phones); prices shown as 2 decimals. Not yet tried on a physical phone.
15:25 — Ayush Rai — Ran the full tests/bills/ corpus and all six typed-text chat cases through the real pipeline.scan_bill/handle_message against the live 4060 for the first time (not raw OCR, not stubs) -- see tests/corpus.md's second results table. Found and fixed 3 bugs this surfaced, two of them the same ones Saket found independently: resolver.py had an unintended non-spec "ambiguous" branch for any mid-range score (fixed -> falls through to "unknown"), the ambiguous candidates list showed top-3 by raw score instead of only genuine near-tie members (fixed -> filtered to the near-tie margin), and extract.py's prompt dropped size/weight from item names, which is how differently-sized variants could silently collide (fixed, took 2 follow-up iterations to avoid regressing other lines). Also fixed seed.py's missing low-stock SKUs (Saket's finding). Traced Saket's "1L12 pouch" report to its root cause: a column-overlap bug in tests/generate_test_bills.py (Ayush Aditya's file, not touched) that makes 2 of 6 printed-01 lines genuinely illegible even to a human -- same bug explains the identical garbling on angle/glare/crumpled-01 since they share the source image. Flagged to Aditya, not fixed (not my file). All offline regression suites (integration/error-path/app-level) still pass after every change.
15:45 — Saket — Price fix in Ayush Rai's files (told to him here): written prices are rupees, converted x100 in code (`rules.trailing_price_paise`, used by `extract.extract_line` and the rule fallback), not by the model; `480/-`, `₹480`, `Rs.480` normalise to 480 (`rules.normalize_price_notation`). Column ledgers (name | qty | price, no unit word) read correctly with the existing OCR prompt. Tried adding a ledger paragraph to `ocr.py`: it garbled Kannada and printed bills, so it was reverted — don't re-add. Open: no-unit lines default to `piece` (or `packet`) regardless of the SKU's own unit; printed bills with the price column FIRST (`920.00 Aashirvaad ... 10kg`) still parse qty=920, price=None.
16:35 — Ayush Rai — Merged `feature/voice-input` (PR #1) into main: `POST /api/voice`, open-source `faster-whisper` (CPU only, never the GPU) transcribes speech and feeds the text into the existing `pipeline.handle_message`/`extract.extract_message` path — no change to the frozen scan/confirm contract. Frontend has an English/हिंदी/ಕನ್ನಡ picker and a "Speak instead" button next to the bill-scan button. This reverses this file's own "voice is cut" decision above — the team's call, made explicitly, not something I decided alone. Verified end-to-end on the live 4060 for Hindi and English (correct transcript -> correct resolution -> correct reply/write). **Kannada is NOT yet validated** — my only Kannada test was synthetic TTS mispronouncing text, not real speech; this needs a native speaker before anyone trusts it for the demo. New dependency for everyone: `faster-whisper` (pulls in `ctranslate2`/`onnxruntime`/`huggingface-hub`) is now in `backend/requirements.txt` — a fresh `pip install` is slower, and `voice.py` also needs system `ffmpeg` and a Hugging Face download on first use of the "small" Whisper model. Also: `faster-whisper`'s own audio decoder is broken on this machine (a PyAV API it calls was removed upstream); worked around with an `ffmpeg` subprocess in `voice.py`, but this has only been verified on this machine, not on Aditya's 4060 — check it there before relying on it.
```
