# Who does what

Times are **relative to when you start** (T+0:00). Written for a ~3h window; extra slack goes
into testing, not new features.

Nobody edits a file they don't own. See the ownership table in `IMPLEMENTATION.md`.

---

## The split, in one line each

| | Owns | One-line brief |
|---|---|---|
| **Saket Kumar Gupta** | Vision + extraction | Make Gemma 4 read a bill photo into clean lines, and make it admit when it can't |
| **Lokesh Ullangula** | Data + resolver | Make the numbers correct, and make the agent ask instead of guess |
| **Ayush Kumar Rai** | API + the review UI | Make it visible, and wire the pieces together |
| **Ayush Aditya** | Bills + delivery | Get real bill photos in the repo, and make the submission complete |

Saket's half and Lokesh's half touch **no shared files**. Ayush Rai owns the only files that
import from both.

---

## T+0:00 → T+0:20 — everyone together, don't split up yet

- [ ] Read `docs/api-contract.md` **out loud, together**. The scan/confirm split is the whole
      design — make sure all four of you can describe it. Fix anything wrong, then freeze it.
- [ ] Everyone clones, everyone can reach `http://172.1.58.57:11434/api/tags`
- [ ] On the 4060: `OLLAMA_MAX_LOADED_MODELS=1`, `ollama list` shows `gemma4:latest`
- [ ] **Ayush Aditya photographs two bills right now** — one printed, one handwritten — and
      pushes them to `tests/bills/`. Saket's gate is blocked on these.
- [ ] Agree the cut list out loud, so cutting later isn't a debate

---

## T+0:20 → T+0:40 — Saket, alone

**The gate.** Four tests from `IMPLEMENTATION.md` § T+0:00 gate. Post results in
`PROGRESS.md` before writing other code:

1. Printed bill → usable one-item-per-line text?
2. **Handwritten bill → how bad is it?** This is the headline risk of the whole project.
3. Full scan latency — under ~8 s?
4. **Non-bill photo → does it say so, or invent items?**

Test 4 matters as much as test 1. A model that hallucinates a delivery from a photo of a wall
is worse than one that reads nothing. Everyone else starts immediately; none of their work
depends on these answers.

---

## Saket — vision and extraction

Files: `llm.py`, `imageprep.py`, `ocr.py`, `extract.py`, `rules.py`

| Time | Task |
|---|---|
| T+0:20 | **The gate** (above). Results to `PROGRESS.md`. |
| T+0:40 | `llm.py` — one `generate()` into Ollama. `temperature: 0`, `num_ctx: 4096`, `think: false`, `keep_alive: "30m"`, `stream: false`. Longer timeout for image calls than text. |
| T+0:55 | `imageprep.py` — **EXIF rotate, downscale to 1024 px, JPEG.** Write this *before* `ocr.py`. It's the difference between a 4-second scan and a 40-second one, and phone photos are routinely sideways. |
| T+1:15 | `ocr.py` — the bill prompt. One item per line, transliterate to Latin, prices as plain numbers, and **`legible: false` rather than inventing items**. Instruct it to skip unreadable lines on handwriting, not guess them. |
| T+1:50 | `extract.py` — `extract_line()` with the pinned schema and **unit enum**. `extract_message()` for the typed-text path. |
| T+2:15 | `rules.py` — regex fallback for bill lines (leading number, unit word, name, trailing price). Handles more printed bills than you'd expect, and costs nothing. Wire as `extract`'s except path, tagged `_source: "rule"`. |
| T+2:35 | Help Ayush Rai integrate. Re-run every bill in `tests/bills/`. |

**Your three traps:** an unconstrained `unit` field (the model will invent `"units"`),
full-resolution images (blows context and latency), and a model that would rather hallucinate
a plausible bill than admit the photo is unreadable.

---

## Lokesh — data and the resolver

Files: `db.py`, `seed.py`, `units.py`, `inventory.py`, `reorder.py`, `resolver.py`, `reply.py`

| Time | Task |
|---|---|
| T+0:20 | `db.py` — the six tables, including `scans`. Money columns are **integer paise**. |
| T+0:45 | `seed.py` — ~30 real kirana SKUs, starting aliases, and **14 days of sales history**. Add `--reset`. The history isn't optional; the low-stock view shows nothing without it. |
| T+1:10 | `units.py` — three-language vocabulary plus **printed-bill abbreviations** (`pkt`, `pc`, `nos`, `dzn`, `bdl`, `jar`, `tin`). `normalize_unit` returns `None` on unknown. Bare `g` is **not** grams. |
| T+1:35 | `inventory.py` — `apply_movement`, and **`apply_scan` as one transaction**. A bill is all-or-nothing; row seven failing must not leave six committed. Price converts by the same ratio as qty. `current_qty` floors at 0. |
| T+2:00 | `resolver.py` — exact alias, fuzzy, **near-tie → ambiguous**, unknown → offer create. `learn_alias` only from the confirm step, never on a fuzzy auto-accept. **Highest-scoring file in the repo.** |
| T+2:30 | `reorder.py` — days of cover. `reply.py` — `scan_summary`, `confirm_summary`, `illegible`, three languages. |

**You can build and test `resolver.py` entirely with fixtures, with no model running.** Don't
wait for Saket.

---

## Ayush Rai — API and the review UI

Files: `main.py`, `config.py`, `pipeline.py`, `routes/*`, `frontend/*`

| Time | Task |
|---|---|
| T+0:20 | `main.py`, `config.py`, and **stub routes** returning the fixtures from the contract — including the `legible: false` one. Push these early. |
| T+0:45 | `frontend/index.html` — the camera/upload button as the **primary action**, not a side feature. Big, obvious, works on a phone viewport. |
| T+1:10 | **Client-side downscale to 1024 px before upload** (canvas), then POST multipart. This is on your side as much as Saket's. |
| T+1:30 | **The review table.** The hardest frontend in the project: a row per line, showing the parsed values, with a dropdown for `ambiguous`, a create option for `unknown`, a unit picker where `unit_ok` is false, editable qty and price, and a skip toggle. Display `raw_text` alongside it. |
| T+2:10 | Handle `legible: false` and `confidence: "low"` — the "check this carefully" banner. Then the confirm POST, and show `aliases_learned` in the result. |
| T+2:30 | `pipeline.py` — `scan_bill` (read-only) and `confirm_scan` (the only writer, idempotent, 409 on a repeat). `run_in_threadpool` from the route. |
| T+2:50 | `dashboard.html` — stock table, low rows red. Cut this if you're behind. |

**Your traps:** forgetting the client-side downscale (every scan gets slow), rendering OCR
text with `innerHTML` (it came from a model, via an image — escape it), and a double-tap on
Confirm booking the bill twice.

---

## Ayush Aditya — bills and delivery

Files: `tests/bills/`, `tests/corpus.md`, `README.md`, screenshots, slides

| Time | Task |
|---|---|
| T+0:00 | **Two bill photos into `tests/bills/`, immediately.** One printed, one handwritten. Saket's gate is blocked on you. Write a handwritten one yourself if you have to — pen and paper, 5–8 items, realistic kirana names and abbreviations. |
| T+0:30 | Four more: a bad-angle one, a glare one, a crumpled one, and **a photo that isn't a bill at all** (for the hallucination guard). Six total. |
| T+1:00 | `tests/corpus.md` — expected items for every bill, so passing or failing is a fact rather than an opinion. |
| T+1:30 | Kannada: a bill with Kannada item names, plus the unit vocabulary verified with a native speaker. Hand corrections to Lokesh. |
| T+2:00 | `README.md` current — what it does, how to run it, **the model and key dependencies**. A scored MLH deliverable, not paperwork. |
| T+2:30 | Demo script written. "Before" dashboard screenshot while stock is still low. |
| T+2:50 | Screenshots of all four demo moments. Backup screen recording. |
| T+3:00 | Slides. Brief every member on their own area. |

**You're on the critical path at minute zero.** Nothing in the vision pipeline can be tested
without real bill photos, and a generated-looking one proves nothing about handwriting.

---

## T+2:50 → T+3:00 — everyone

- [ ] Every bill in `tests/bills/` scanned end to end
- [ ] A bill with an ambiguous line: dropdown → confirm → **scan the same bill again** → now
      resolves silently. That contrast is the pitch.
- [ ] The non-bill photo correctly refused
- [ ] Double-tap Confirm → 409, not a double booking
- [ ] `python -m app.seed --reset`, then final screenshots on clean data
- [ ] Backup recording saved. Everything pushed.
- [ ] Pitch rehearsed twice, out loud

---

## The demo, four moments

1. **Scan a printed bill.** Camera → review table fills in → confirm → dashboard updates.
2. **The ambiguous line.** Point at the dropdown. "It doesn't know which Maggi, so it asks
   instead of guessing."
3. **Scan the same bill again.** The line that needed asking now resolves silently. *"It
   learned."*
4. **Scan something that isn't a bill.** It refuses. "It would rather read nothing than
   invent a delivery."

Moment 4 is the one judges remember, because almost nothing else at a hackathon declines to
answer.

---

## Rules of engagement

1. **The contract is frozen at T+0:20.** After that, a field-name change gets announced to
   all three others before you push.
2. **Nobody waits.** Stubs exist from T+0:45. Build against them.
3. **Stay in your own files.** Need something changed elsewhere? Ask the owner.
4. **Commit every ~30 minutes**, push every time.
5. **Update `PROGRESS.md` when you finish a chunk.** One line in the log. The next person —
   or the next AI session when context runs out — reads that file to pick up.
6. **Protect T+1:30 → T+2:10 (review table) and T+2:00 → T+2:30 (resolver).** Those two are
   the highest-scoring work in the project. Don't let integration eat them.
7. **Behind at T+2:30? Cut from the list.** Don't negotiate. The order is already agreed.
