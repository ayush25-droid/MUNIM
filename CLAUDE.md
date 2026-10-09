# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Munim is a hackathon project (Hacktoberfest Hack Day Bengaluru '26, Track 2: open-weight AI). Shopkeepers photograph a supplier bill (handwritten or printed; Kannada, Hindi or English), and the agent updates the shop's inventory ledger after a human confirms.

**So far the repo holds planning docs only. `backend/` and `frontend/` don't exist yet.** These docs are the source of truth. Read the relevant one before writing code:

- `docs/api-contract.md`: **frozen** API shapes and stub fixtures. Don't change a field name unilaterally.
- `IMPLEMENTATION.md`: module contracts (function signatures and return shapes), DB schema, hardware limits, build order, and cut list.
- `TASKS.md`: who owns which files. **Nobody edits a file they don't own.** Ask before touching another owner's files.
- `PROGRESS.md`: the live handoff file. When you finish a chunk, tick boxes and append one line to the log (`HH:MM — who — what`). Record gotchas in "Known issues". Its "Decisions made — don't relitigate" table is settled.
- `tests/corpus.md`: bill test cases, pass criteria, and the unit vocabulary.

Ownership conflict: `IMPLEMENTATION.md` module-contract headings still credit `llm.py`/`imageprep.py`/`ocr.py`/`extract.py`/`rules.py` to Saket. The file tree, `TASKS.md` and the latest commit assign them to Ayush Rai. Trust the file tree and `TASKS.md`.

## Commands (planned layout, from README)

```bash
# backend (Python 3.11+, FastAPI, SQLite)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env            # set OLLAMA_HOST; use localhost on the GPU laptop
python -m app.seed                 # demo shop, ~30 SKUs, 14 days of history
python -m app.seed --reset         # reset a dirty demo DB
uvicorn app.main:app --reload --port 8000

# frontend: plain HTML/CSS/vanilla JS, no build step, no npm
cd frontend && python3 -m http.server 5500
```

No test runner has been chosen yet. Bill tests are manual, run against `tests/corpus.md` with photos in `tests/bills/`. `resolver.py` is meant to be unit-testable with fixtures and no model.

## Architecture

```
photo -> imageprep (EXIF rotate, 1024px) -> ocr (vision -> Latin text lines) -> extract (line -> item)
      -> units.normalize_unit -> resolver.resolve -> pending scan  ||  CONFIRM -> inventory.apply_scan
```

- **`POST /api/scan` is read-only.** It stores the result as a `pending` row in `scans` and returns a review payload. **`POST /api/scan/confirm` is the only endpoint that writes the ledger.** It's idempotent: repeat confirms return 409. `apply_scan` runs as a single all-or-nothing transaction.
- `pipeline.py` (`scan_bill`, `confirm_scan`, `handle_message`) is the only module that imports across ownership boundaries. Routes call it via `starlette.concurrency.run_in_threadpool`, since SQLite and Ollama calls are sync.
- The vision step outputs **plain text lines, not structured data**. The text then goes through the same extract → resolve path as typed `/api/chat` messages. `extract.py` falls back to the regex extractor in `rules.py` (English and Hindi only, no Kannada) on any failure, never raises, and tags each result `_source: "llm" | "rule"`.
- OCR **transliterates everything to lowercase Latin script**. The resolver, alias table and units therefore stay script-agnostic, and one alias row covers all three languages.
- `ocr.read_bill` returns `legible: false` on a non-bill or unreadable photo, and the pipeline returns early with no items. Inventing line items is the worst possible failure.

### Resolver rules (`resolver.py`)
Statuses in order: `exact` (alias hit) → `fuzzy` (top match above the threshold *and* clearly ahead of second) → `ambiguous` (top two within ~5 points, **however high the top score is**) → `unknown`. `learn_alias` is called **only from the confirm step**, when a human picked the SKU. A fuzzy auto-accept must never write an alias.

## Invariants that bind every module

- **Money is integer paise** everywhere: DB, API, internal code.
- `unit` must be one of `packet box sack dozen kg gram litre piece`. Extraction enforces this with a schema enum. `normalize_unit` returns `None` for unrecognised units and never passes them through. Bare `g` is **not** grams (it would break `parle g`). Conversions are per-SKU. Price converts by the same ratio as quantity. `current_qty` floors at 0.
- A `query` intent never writes stock (e.g. `"2 kg aata chahiye"` is a request, not a delivery). Booking a stock-out needs an explicit sale verb.
- The frontend escapes all API output (`escapeHtml`, never raw `innerHTML`), downscales images to 1024 px before upload, and guards Confirm against in-flight double taps.
- Errors always return a real status code with a `{"error": ...}` body, never a 200 that wraps an error.

## Hardware limits (Ollama, `gemma4:latest`, RTX 4060 with 8 GB)

One model handles both vision and text. Breaking any of these rules OOMs or stalls the demo:
- Only one model may be loaded at a time (`OLLAMA_MAX_LOADED_MODELS=1`).
- `num_ctx` 4096. The model advertises 131072, and requesting that OOMs.
- Downscale images to 1024 px, both client-side and server-side.
- `think: false`, `keep_alive: "30m"`, `temperature: 0`, `stream: false`.
- If vision OOMs, drop `num_ctx` to 2048 first, then downscale images to 768 px.

Settings live in `.env.example` (`OLLAMA_HOST`, `OLLAMA_NUM_CTX`, `IMAGE_MAX_EDGE`, `LLM_TIMEOUT`, `LLM_VISION_TIMEOUT`, `MAX_UPLOAD_MB`, ...).
