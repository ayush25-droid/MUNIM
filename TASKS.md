# Who does what

Times are **relative to when you start** (T+0:00). Written for a ~2h30 window; extra slack
goes into testing, not new features.

Nobody edits a file they don't own.

---

## The split

| | Owns | One-line brief |
|---|---|---|
| **Ayush Kumar Rai** | The spine — vision, extraction, orchestration | The code-heavy core: photo in, resolved items out, nothing written until approved |
| **Saket Kumar Gupta** | API + the review UI | Make it visible and operable. The review table is the hardest frontend here. |
| **Lokesh Ullangula** | Data + resolver | Make the numbers correct, and make the agent ask instead of guess |
| **Ayush Aditya** | **The machine**, bills, QA, delivery | He has the 4060. Everything runs on his laptop, so he owns the model, the test bills, and the demo. |

The four file sets **do not overlap**. Ayush Rai's `pipeline.py` is the only file that imports
across boundaries.

### Why this shape

- **Ayush Rai has Claude**, so he takes the largest and most intricate code: the whole
  vision → extraction → orchestration spine.
- **Ayush Aditya has the GPU.** The model lives on his machine, the demo runs on his machine,
  and final integration happens on his machine. That is a real job, not a support role — if
  his laptop isn't running the full stack by T+1:30, the project has no demo.
- **Lokesh's half needs no model at all.** The resolver is pure logic, testable with fixtures.
- **Saket's half needs no backend.** Stubs exist from T+0:30.

---

## T+0:00 → T+0:15 — everyone together

- [ ] Read `docs/api-contract.md` **out loud together**. The scan/confirm split is the whole
      design. Fix anything wrong, then freeze it.
- [ ] Everyone can reach `http://172.1.58.57:11434/api/tags`
- [ ] Ayush Aditya sets `OLLAMA_MAX_LOADED_MODELS=1` and confirms `ollama list`
- [ ] **Ayush Aditya photographs two bills immediately** — one printed, one handwritten —
      and pushes them. Ayush Rai is blocked on these.
- [ ] Cut list agreed out loud, so cutting later isn't a debate

---

## Ayush Kumar Rai — the spine

Files: `llm.py`, `imageprep.py`, `ocr.py`, `extract.py`, `rules.py`, `pipeline.py`

You have the most code and the most intricate logic. You're also iterating against a GPU on
someone else's laptop over the LAN, so batch your experiments rather than round-tripping one
prompt tweak at a time.

| Time | Task |
|---|---|
| T+0:15 | `llm.py` — one `generate()` into Ollama. `temperature: 0`, `num_ctx: 4096`, `think: false`, `keep_alive: "30m"`, `stream: false`. Separate timeouts for text and vision. |
| T+0:30 | `imageprep.py` — **EXIF rotate, downscale to 1024 px, JPEG.** Write this *before* `ocr.py`. It's the difference between a 4-second scan and a 40-second one, and phone photos are routinely sideways. |
| T+0:45 | `ocr.py` — the bill prompt. One item per line, transliterate to Latin, prices as plain numbers, and **`legible: false` rather than inventing items**. On handwriting, instruct it to skip unreadable lines rather than guess, and report `confidence: "low"`. |
| T+1:20 | `extract.py` — `extract_line()` with the pinned schema and **unit enum**, plus `extract_message()` for the typed-text path. |
| T+1:40 | `rules.py` — regex fallback for bill lines (leading number, unit word, name, trailing price). Handles more printed bills than you'd expect. Wire as `extract`'s except path, tagged `_source: "rule"`. |
| T+1:55 | `pipeline.py` — `scan_bill` (read-only) and `confirm_scan` (the only writer, idempotent, 409 on repeat). `run_in_threadpool` from Saket's route. |
| T+2:15 | Integrate with Saket. Run every bill in `tests/bills/`. |

**Your four traps:** an unconstrained `unit` field (the model invents `"units"`),
full-resolution images (blows context and latency), a model that would rather hallucinate a
plausible bill than admit the photo is unreadable, and a double-tap on Confirm booking the
bill twice.

---

## Saket Kumar Gupta — API and the review UI

Files: `main.py`, `config.py`, `routes/*`, all of `frontend/`

| Time | Task |
|---|---|
| T+0:15 | `main.py`, `config.py`, and **stub routes** returning the fixtures from the contract — including the `legible: false` one. Push these first; they unblock your own frontend. |
| T+0:35 | `index.html` — camera/upload as the **primary action**, not a side button. Big, obvious, works at phone width. |
| T+0:55 | **Client-side downscale to 1024 px before upload** (canvas), then POST multipart. Don't skip this because the server also does it — the upload itself needs to be small on venue wifi. |
| T+1:15 | **The review table.** The hardest frontend in the project: a row per line showing parsed values, a dropdown for `ambiguous`, a create option for `unknown`, a unit picker where `unit_ok` is false, editable qty and price, and a skip toggle. Show `raw_text` alongside it. |
| T+1:55 | Handle `legible: false` and `confidence: "low"` — the check-carefully banner. Then the confirm POST, and display `aliases_learned` in the result. |
| T+2:10 | Swap stubs for Ayush Rai's real pipeline. |
| T+2:25 | `dashboard.html` — stock table, low rows red. **Cut this if you're behind.** |

**Your traps:** rendering OCR text with `innerHTML` (it came from a model via an image —
escape it), and no in-flight guard on Confirm.

---

## Lokesh Ullangula — data and the resolver

Files: `db.py`, `seed.py`, `units.py`, `inventory.py`, `reorder.py`, `resolver.py`, `reply.py`

**You need no model and no frontend. Nothing blocks you at any point.**

| Time | Task |
|---|---|
| T+0:15 | `db.py` — six tables including `scans`. Money columns are **integer paise**. |
| T+0:35 | `seed.py` — ~30 real kirana SKUs, starting aliases, and **14 days of sales history**. Add `--reset`. The history isn't optional; the low-stock view shows nothing without it. |
| T+1:00 | `units.py` — three-language vocabulary plus **printed-bill abbreviations** (`pkt`, `pc`, `nos`, `dzn`, `bdl`, `ctn`, `jar`, `tin`). `normalize_unit` returns `None` on unknown. Bare `g` is **not** grams. |
| T+1:20 | `inventory.py` — `apply_movement`, and **`apply_scan` as one transaction**. A bill is all-or-nothing; row seven failing must not leave six committed. Price converts by the same ratio as qty. `current_qty` floors at 0. |
| T+1:45 | `resolver.py` — exact alias, fuzzy, **near-tie → ambiguous**, unknown → offer create. `learn_alias` only from the confirm step, never on a fuzzy auto-accept. **Highest-scoring file in the repo.** |
| T+2:15 | `reorder.py` — days of cover. `reply.py` — `scan_summary`, `confirm_summary`, `illegible`, three languages. |

Build and test `resolver.py` entirely with fixtures. Don't wait for anyone.

---

## Ayush Aditya — the machine, bills, QA, delivery

You own the 4060, which means you own the model, the test corpus, the integration host, and
the demo. **This is the operational critical path.** If your laptop isn't running the whole
stack by T+1:30, there is no demo regardless of how good everyone else's code is.

| Time | Task |
|---|---|
| T+0:00 | **Two bill photos, immediately** — one printed, one handwritten, pushed to `tests/bills/`. Ayush Rai is blocked on you. Write the handwritten one yourself: pen and paper, 5–8 items, real kirana names, supplier abbreviations (`pkt`, `dzn`, `kg`, `nos`). Don't print it neatly — that defeats the test. |
| T+0:20 | **The gate.** Four tests against the model, results into `PROGRESS.md`: printed bill readable? handwritten readable? scan latency? **does a non-bill photo get refused or hallucinated?** These four answers decide what ships. |
| T+0:50 | Four more bills: bad angle, glare, crumpled, and **a photo that isn't a bill at all**. Six total. |
| T+1:10 | `tests/corpus.md` — the expected items for every bill, written from the bill itself, so passing is a fact rather than an opinion. |
| T+1:30 | **Get the full stack running on your laptop** — clone, backend, seed, frontend, all of it. Don't wait for the code to be finished; run what exists and keep re-pulling. Integration failures found now are cheap; found at T+2:30 they are fatal. |
| T+1:50 | Kannada: a bill with Kannada item names, plus the unit vocabulary verified with a native speaker. Hand corrections to Lokesh. |
| T+2:10 | Run every bill through the real pipeline. Record pass/fail in the corpus. You are the QA loop. |
| T+2:25 | Four demo screenshots. Backup screen recording. Demo script written. |
| T+2:40 | Slides. Brief every member on their own area. |

**Keep Ollama healthy throughout.** If it gets unloaded, restarted, or a second model gets
pulled onto it, everyone else's work stops. That's your service to run.

---

## T+2:30 → T+2:45 — everyone, on Ayush Aditya's laptop

- [ ] Every bill in `tests/bills/` scanned end to end
- [ ] Ambiguous line: dropdown → confirm → **re-scan the same bill** → resolves silently
- [ ] The non-bill photo correctly refused
- [ ] Double-tap Confirm → 409, not a double booking
- [ ] `python -m app.seed --reset`, then final screenshots on clean data
- [ ] Backup recording saved. Everything pushed.
- [ ] Pitch rehearsed twice, out loud

---

## The demo, four moments

1. **Scan a printed bill.** Camera → review table fills → confirm → dashboard updates.
2. **The ambiguous line.** Point at the dropdown: *"it doesn't know which Maggi, so it asks
   instead of guessing."*
3. **Scan the same bill again.** That line now resolves silently. *"It learned."*
4. **Scan something that isn't a bill.** It refuses. *"It would rather read nothing than
   invent a delivery."*

Moment 4 is the one judges remember, because almost nothing else at a hackathon declines to
answer.

---

## Rules of engagement

1. **The contract is frozen at T+0:15.** After that, a field-name change gets announced to
   all three others before you push.
2. **Nobody waits.** Stubs from T+0:30. Lokesh and Saket are never blocked at all.
3. **Stay in your own files.** Need something changed elsewhere? Ask the owner.
4. **Commit every ~30 minutes**, push every time.
5. **Update `PROGRESS.md` when you finish a chunk.** One line in the log. The next person —
   or the next AI session when context runs out — reads that file to pick up.
6. **Protect T+1:15 → T+1:55 (review table) and T+1:45 → T+2:15 (resolver).** Highest-scoring
   work in the project. Don't let integration eat them.
7. **Behind at T+2:00? Cut from the list.** Don't negotiate. The order is already agreed.
