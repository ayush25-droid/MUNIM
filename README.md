# Munim

**An open-weight AI agent that keeps a kirana shop's stock register from speech — in
Kannada, Hindi, or English.**

Hacktoberfest Hack Day Bengaluru '26 · Track 2 — Best Open-Source AI Project
PS 03 — Open-Source AI Agent for Real-World Operations
Team Hold_The_Door · MIT licence

A *munim* is the bookkeeper who keeps a shop's accounts. That's the job this agent does.

---

## What it does

The shop owner sends a voice note, the way they already talk:

> "aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya — chhiyalis rupaye"

The agent works out what they meant, writes two ledger entries with two different units,
saves the new price against the right column, and replies with a confirmation.

When it isn't sure, it asks — **once**:

> **Owner:** do amul aaye
> **Munim:** Amul Butter ya Amul Milk?
> **Owner:** butter
> **Munim:** 2 packet Amul Butter likh diya. Aage se "amul" ka matlab yahi samjhunga.

That answer is written to an alias table, so the question is never asked again. The agent
gets quieter the longer the shop uses it.

And before stock runs out, it speaks first:

> Parle-G 3 din mein khatam ho jayega. Order bhej doon?

## The problem

India has roughly 13 million kirana stores and almost none of them use inventory software.
This is consistently misdiagnosed as a user-experience failure. It isn't.

A shop owner has a customer at the counter, a delivery at the door, and one pair of hands.
Typing thirty SKUs into an app isn't a task that competes badly for their attention — it's
a task for which the time does not exist. Every inventory product aimed at this segment
dies in the same place: **data entry**.

What they already do all day is talk. Voice notes are the default medium for this entire
segment of Indian commerce, so the input channel is already solved and needs no training.

## The hard part

Not the speech. **The names.**

One shop calls the same biscuit `parle g`, `parle-g`, `chhota parle`, `पारले जी`,
`ಪಾರ್ಲೆ-ಜಿ`. Units are worse — packet, box, sack, dozen, kg, gram, litre, piece — and
conversions are **per-SKU**, not global: a box of Coke is 24, a box of something else isn't.

The failure mode is what makes it dangerous. A wrong match doesn't raise an error. It
silently writes a correct-looking number against the wrong item, and the books drift quietly
away from reality. There is no stack trace for "you decremented the wrong SKU three weeks
ago."

Everything in the design follows from that one fact — which is why the agent treats
**refusing to act** as a first-class outcome rather than an error.

## How the multilingual part works

The extraction model emits item names in **Latin script**, transliterated, whatever script
came in. So `ಪಾರ್ಲೆ-ಜಿ`, `पारले जी` and `parle g` all reach the resolver as `parle g`.

That one decision keeps the resolver, the alias table and the unit layer completely
script-agnostic. **One alias row serves all three languages** — a Kannada speaker's answer
to a clarifying question also teaches the Hindi path.

The alternative would have been embeddings or per-script alias rows, both of which cost
considerably more.

## Architecture

```
intake  ->  transcribe  ->  extract  ->  resolve  ->  write  ->  reply
voice       Gemma 4         Gemma 4      alias       atomic     in the
photo       audio /         + JSON       fuzzy       ledger     detected
text        vision          schema       ask-once    write      language
```

One model does all of it. `gemma4:latest` reports `completion`, `vision`, `audio`, `tools`
and `thinking`, which collapses what was going to be a three-model stack into one and keeps
us inside the GPU's 8 GB.

See [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) for the full architecture and module contracts.

## The model

| Job | Model | Open weights |
|---|---|---|
| Speech → text | `gemma4:latest` (audio input) | Yes |
| Text → structured JSON + romanisation | `gemma4:latest` (schema-constrained) | Yes |
| Bill photo → text | `gemma4:latest` (vision) | Yes |

Served locally through [Ollama](https://ollama.com). Nothing proprietary sits anywhere in
the pipeline — Gemma 4 is open-weight, which is what Track 2 requires. The same code runs
against any hosted open-weight endpoint by changing one environment variable.

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

### Key dependencies

| | |
|---|---|
| Runtime | Python 3.11+, FastAPI, Uvicorn, SQLite |
| Inference | Ollama, `gemma4:latest` (Q4_K_M, 7.5B) |
| Matching | `rapidfuzz` |
| Frontend | Plain HTML + CSS + vanilla JS, no framework |

### GPU note

Tested on an RTX 4060 Laptop (8 GB, ~6.9 GB usable). The model is ~6.1 GB at Q4_K_M, so
**keep `num_ctx` at 4096 and never load a second model alongside it.** See the hardware
section of `IMPLEMENTATION.md`.

## Known limitations

Stated plainly rather than discovered by a judge:

- **Kannada has no rule-based fallback.** The keyword fallback extractor covers English and
  Hindi only, so Kannada runs model-only. A Kannada message the model can't parse produces
  an honest "didn't understand" — never a wrong ledger write.
- **Kannada speech recognition is unverified.** Kannada *text* works; Kannada *voice*
  depends on ASR quality we're still evaluating.
- **One hardcoded demo shop.** No authentication, no multi-tenancy.
- **No barcode scanning.** Most kirana stock — loose grains, local brands, repacked goods —
  isn't barcoded.

## Docs

| File | What's in it |
|---|---|
| [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) | Architecture, hardware limits, module contracts, build order |
| [`TASKS.md`](./TASKS.md) | Who does what, hour by hour |
| [`docs/api-contract.md`](./docs/api-contract.md) | Frozen API shapes — read before coding |
| [`PROGRESS.md`](./PROGRESS.md) | Live status. Update as you work. |

## Team

| | Owns |
|---|---|
| Saket Kumar Gupta | Model layer — extraction, fallback, replies |
| Lokesh Ullangula | Data model, units, ledger, resolver |
| Ayush Kumar Rai | API, frontend, pipeline orchestration |
| Ayush Aditya | Language verification, documentation, delivery |

## Licence

MIT. See [`LICENSE`](./LICENSE).
