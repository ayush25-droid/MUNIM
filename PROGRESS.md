# Progress

**Everyone: update this as you finish things.** Some of us are using AI agents that will run
out of context. When a new session starts, this file is the handoff.

How to use it: tick your boxes, and append **one line** to the log at the bottom with the
time. Facts, not prose — the next reader needs what's true now, not a narrative.

---

## Status at a glance

| | Current task | Blocked on | Last pushed |
|---|---|---|---|
| **Saket** — model layer | the T+0:20 gate | nothing | — |
| **Lokesh** — data + resolver | `db.py` | nothing | — |
| **Ayush Rai** — API + frontend | stub routes | nothing | — |
| **Ayush Aditya** — language + delivery | `tests/corpus.md` | finding a Kannada speaker | — |

**Overall: T+0:00. Nothing built yet.**

---

## The gate — fill this in first

Saket answers these before anything else gets built. They decide what ships.

| Test | Result | Decision |
|---|---|---|
| Text extraction correct in **en**? | — | |
| Text extraction correct in **hi**? | — | |
| Text extraction correct in **kn**? | — | if no → Kannada is cut |
| Names returned in **Latin script**? | — | if no → the multilingual strategy needs rethinking |
| **Audio** transcript usable? | — | if no → voice is hi/en only, or typed text |
| Round trip under **~4 s**? | — | if no → check `think`, `num_ctx`, cold load |

---

## Checklist

### Shared — T+0:00 → T+0:20
- [ ] `docs/api-contract.md` read out loud together and frozen
- [ ] Everyone can reach `http://172.1.58.57:11434/api/tags`
- [ ] `OLLAMA_MAX_LOADED_MODELS=1` set on the 4060
- [ ] `ollama list` confirms `gemma4:latest`
- [ ] First commit pushed
- [ ] Cut list agreed out loud

### Saket — model layer
- [ ] The gate, results posted above
- [ ] `llm.py` — `generate()` into Ollama, `think: false`, `num_ctx: 4096`, `keep_alive: "30m"`
- [ ] `extract.py` — pinned schema with unit **enum**, romanisation instruction
- [ ] `rules.py` — keyword fallback, en + hi
- [ ] Fallback wired as `extract()`'s except path, tagged `_source: "rule"`
- [ ] `reply.py` — `confirm`, `ask_sku`, `ask_unit`, `not_understood`, three languages
- [ ] Corpus passing end to end

### Lokesh — data + resolver
- [ ] `db.py` — six tables, money in integer paise
- [ ] `seed.py` — ~30 SKUs + starting aliases
- [ ] `seed.py` — **14 days of sales history** (the low-stock alert needs this)
- [ ] `seed.py --reset`
- [ ] `units.py` — three-language vocabulary, per-SKU conversions
- [ ] `units.py` — bare `g` is not grams; `normalize_unit` returns `None` on unknown
- [ ] `inventory.py` — `apply_movement`, one connection one commit
- [ ] `inventory.py` — price converts by the same ratio as qty; direction picks the column
- [ ] `inventory.py` — `current_qty` floors at 0
- [ ] `resolver.py` — exact alias
- [ ] `resolver.py` — fuzzy
- [ ] `resolver.py` — **near-tie → ask**
- [ ] `resolver.py` — `learn_alias` only on human confirmation
- [ ] `reorder.py` — days of cover, suggested qty net of `current_qty`

### Ayush Rai — API + frontend + glue
- [ ] `main.py`, `config.py`
- [ ] Stub routes returning contract shapes — **pushed early**
- [ ] `index.html` + `app.js` — chat UI, looks real
- [ ] Options send `value` not `label`
- [ ] In-flight guard, `escapeHtml`, `sender` from `sessionStorage`, `res.ok` checked
- [ ] `dashboard.html` + `dashboard.js` — low rows red
- [ ] `pipeline.py` — pending row cleared **before** parsing
- [ ] `pipeline.py` — intent gate (a query never writes)
- [ ] `pipeline.py` — shared `_apply_item()` for both paths
- [ ] `pipeline.py` — `run_in_threadpool` from the route
- [ ] Stubs swapped for the real pipeline

### Ayush Aditya — language + delivery
- [ ] Kannada speaker found
- [ ] `tests/corpus.md` — 9 sentences (en/hi/kn × multi, ambiguous, query)
- [ ] Kannada unit vocabulary verified, corrections handed to Lokesh
- [ ] Kannada extraction output judged correct
- [ ] `README.md` current — what it does, how to run, model + dependencies
- [ ] Demo script written
- [ ] "Before" dashboard screenshot taken while stock is low
- [ ] Four demo screenshots
- [ ] Backup recording
- [ ] Slides, every member briefed on their own area

### Endgame — everyone, T+3:00
- [ ] Full flow ten times, all three languages
- [ ] Ask-once verified: ask → answer → same message again → silent
- [ ] A refusal verified: unrecognised unit writes nothing
- [ ] `seed.py --reset` then final screenshots
- [ ] Everything pushed

---

## Decisions made — don't relitigate

| Decision | Reason |
|---|---|
| One model (`gemma4:latest`) for audio, vision and text | 6.9 GB usable VRAM won't hold two. Also less to integrate. |
| `num_ctx` stays 4096 | Model advertises 131072; requesting it OOMs instantly |
| `think: false` | Extended reasoning costs seconds we don't have; this is extraction, not reasoning |
| Near-tie rule in the resolver | `amul` scores ~90 against both Butter and Milk; picking the top silently books the wrong item |
| Fuzzy auto-accept never writes an alias | No human confirmed it. Temporarily wrong is fine; permanently wrong is not. |
| Romanise at extraction | Keeps the resolver and alias table script-agnostic. One alias row serves three languages. |
| Money as integer paise | Float rupees produce wrong totals |
| SQLite, not Postgres | No service to run, nothing to provision |
| `rapidfuzz`, not embeddings | Good enough for kirana names, zero setup |
| Plain HTML, no React | No build step to break at hour three |
| No barcode scanning | Most kirana stock isn't barcoded |
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
