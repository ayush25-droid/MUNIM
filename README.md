# Munim

**Photograph a supplier bill. The inventory updates.**

An open-weight AI agent that reads handwritten or printed kirana shop bills — in Kannada,
Hindi, or English — and keeps the stock register from them.

Hacktoberfest Hack Day Bengaluru '26 · Track 2 — Best Open-Source AI Project
PS 03 — Open-Source AI Agent for Real-World Operations
Team Hold_The_Door · MIT licence

A *munim* is the bookkeeper who keeps a shop's accounts. That's the job this agent does.

---

## What it does

A delivery arrives with a bill — often handwritten on a pad, sometimes printed. The shopkeeper
opens the web app, taps the camera, and photographs it.

The agent reads the bill, works out which catalogue item each line refers to, and shows what
it understood:

| Line read | Matched to | |
|---|---|---|
| `20 pkt Parle-G 480` | Parle-G Biscuit | matched |
| `2 dzn Maggi 240` | **Maggi Noodles / Maggi Masala?** | needs you |
| `5 kg Aashirvaad Atta 4600` | Aashirvaad Atta | matched |

The shopkeeper picks the right Maggi, taps Confirm, and the ledger updates. **Next time, that
line resolves on its own** — the answer was written to an alias table, so the agent asks once
and never again.

It gets quieter the longer the shop uses it.

## The problem

India has roughly 13 million kirana stores and almost none of them use inventory software.
This is consistently misdiagnosed as a user-experience failure. It isn't.

A shop owner has a customer at the counter, a delivery at the door, and one pair of hands.
Typing thirty SKUs into an app isn't a task that competes badly for their attention — it's a
task for which the time does not exist. Every inventory product aimed at this segment dies in
the same place: **data entry**.

But the bill is already in their hand. It's the one moment where the data exists in physical
form, at exactly the time stock changes. Reading it costs the shopkeeper one photo.

## The hard part

Not the OCR. **The names.**

Bills use shop shorthand. One supplier writes `Parle G`, another `parle-g`, another
`चोटा पारले`, another `ಪಾರ್ಲೆ-ಜಿ`. Units are worse — `pkt`, `dzn`, `peti`, `bori`, `nos`,
`bdl` — and conversions are **per-SKU**, not global: a box of Coke is 24, a box of something
else isn't.

The failure mode is what makes it dangerous. A wrong match doesn't raise an error. It silently
writes a correct-looking number against the wrong item, and the books drift quietly away from
reality. There is no stack trace for "you credited the wrong SKU three weeks ago."

So the agent is built around a single principle: **when a wrong guess would corrupt the books,
ask.** A scan writes nothing until a human approves it, a near-tie is always a question rather
than a coin-flip, and a photo it can't read gets an honest refusal instead of an invented
delivery.

## How the multilingual part works

The OCR step transliterates item names into **Latin script**, whatever script the bill is
written in. So `ಪಾರ್ಲೆ-ಜಿ`, `पारले जी` and `Parle G` all reach the resolver as `parle g`.

That one decision keeps the resolver, the alias table and the unit layer completely
script-agnostic. **One alias row serves all three languages.** The alternative — embeddings,
or per-script alias rows — costs considerably more for no extra capability.

## Architecture

```
  photo  ->  downscale  ->  vision  ->  extract  ->  resolve  ->  CONFIRM  ->  ledger
             1024px         -> text      -> items     -> sku      human        atomic
             EXIF fix       lines        per line     or options  approves     write
             ------------------- no side effects -------------------|
```

Everything left of Confirm is read-only. Abandoning a scan costs nothing. One endpoint writes.

The vision step deliberately produces **plain text**, not final structured data, so the same
extraction and resolution path serves bills and typed messages alike — and so the transcript
can be shown to the shopkeeper for correction before anything is committed.

See [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) for module contracts and the hardware limits.

## The model

| Job | Model | Open weights |
|---|---|---|
| Bill photo → text | `gemma4:latest` (vision) | Yes |
| Text → structured item + transliteration | `gemma4:latest` (schema-constrained) | Yes |

One model, both jobs. Served locally through [Ollama](https://ollama.com). Nothing proprietary
sits anywhere in the pipeline — Gemma 4 is open-weight, which is what Track 2 requires. The
same code runs against any hosted open-weight endpoint by changing one environment variable.

## Running it

Requires [Ollama](https://ollama.com) with `gemma4:latest` pulled, and Python 3.11+.

```bash
# backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # point OLLAMA_HOST at your Ollama
python -m app.seed             # demo shop, ~30 SKUs, 14 days of history
uvicorn app.main:app --reload --port 8000

# frontend — no build step, no npm
cd frontend && python3 -m http.server 5500
# open http://localhost:5500
```

Reset a dirty demo database with `python -m app.seed --reset`.

### Running on Windows (PowerShell)

Install Python 3.11+, Git and [Ollama](https://ollama.com). For voice input also install
ffmpeg (`winget install Gyan.FFmpeg`, then reopen the terminal).

```powershell
# once: keep a single model resident on the 8 GB GPU, then restart Ollama from the tray
setx OLLAMA_MAX_LOADED_MODELS 1
ollama pull gemma4:latest

# backend
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
copy ..\.env.example .env            # set OLLAMA_HOST=http://localhost:11434 when Ollama is on this machine
$env:PYTHONUTF8 = 1                  # stops the console crashing on Hindi/Kannada text
python -m app.seed
uvicorn app.main:app --host 0.0.0.0 --port 8000

# frontend, in a second terminal
cd frontend
python -m http.server 5500
```

Check `http://localhost:8000/api/health` returns `"stubs":false`, then open
`http://localhost:5500`. The first scan takes about 70 s while the model loads.

**Testing from a phone.** Put the phone on the same network, find the laptop's address with
`ipconfig`, and allow the ports once in an Administrator PowerShell:
`New-NetFirewallRule -DisplayName "Munim" -Direction Inbound -Protocol TCP -LocalPort 8000,5500 -Action Allow`.
Then open `http://<laptop-ip>:5500/index.html?api=http://<laptop-ip>:8000`.

**Voice.** The first voice request downloads the Whisper `small` model (about 500 MB), so do
it once on good wifi beforehand. Browsers generally block the microphone on plain `http://`
pages other than `localhost`, so use voice from the laptop's own browser. Photo scanning
works from a phone either way.

### Key dependencies

| | |
|---|---|
| Runtime | Python 3.11+, FastAPI, Uvicorn, SQLite |
| Inference | Ollama, `gemma4:latest` (Q4_K_M, 7.5B) |
| Image prep | Pillow |
| Matching | `rapidfuzz` |
| Frontend | Plain HTML + CSS + vanilla JS, no framework |

### GPU note

Tested on an RTX 4060 Laptop (8 GB, ~6.9 GB usable). The model is ~6.1 GB at Q4_K_M, so:
**keep `num_ctx` at 4096, never load a second model, and downscale every image to 1024 px
before sending it.** A full-resolution phone photo will blow the context window and make
inference crawl. See the hardware section of `IMPLEMENTATION.md`.

## Known limitations

Stated plainly rather than left for a judge to find:

- **Handwritten bills are harder than printed ones.** Legibility, angle and glare all matter.
  The agent reports low confidence and asks the shopkeeper to check carefully rather than
  pretending otherwise.
- **Kannada has no rule-based fallback.** The regex/keyword fallback covers English and Hindi,
  so Kannada runs model-only. A line it can't parse produces a flagged row for the shopkeeper,
  never a silent wrong write.
- **One hardcoded demo shop.** No authentication, no multi-tenancy.
- **No barcode scanning.** Most kirana stock — loose grains, local brands, repacked goods —
  isn't barcoded, which is why the bill is the better input.

## Docs

| File | What's in it |
|---|---|
| [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) | Architecture, hardware limits, module contracts, build order |
| [`TASKS.md`](./TASKS.md) | Who does what, hour by hour |
| [`docs/api-contract.md`](./docs/api-contract.md) | Frozen API shapes — read before coding |
| [`PROGRESS.md`](./PROGRESS.md) | Live status. Update as you work. |
| [`tests/corpus.md`](./tests/corpus.md) | Bill test cases and expected results |

## Team

| | Owns |
|---|---|
| Ayush Kumar Rai | Vision, image prep, extraction, fallback, pipeline orchestration |
| Saket Kumar Gupta | API routes and the review UI |
| Lokesh Ullangula | Data model, units, ledger, resolver, replies |
| Ayush Aditya | Inference host, bill corpus, language verification, QA, delivery |

## Licence

MIT. See [`LICENSE`](./LICENSE).
