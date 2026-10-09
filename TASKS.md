# Who does what

Times are **relative to when you start** (T+0:00). Written for a ~3h30 window; if you have
more, the slack goes into testing, not new features.

Nobody edits a file they do not own. See the ownership table in `IMPLEMENTATION.md`.

---

## The split, in one line each

| | Owns | One-line brief |
|---|---|---|
| **Saket Kumar Gupta** | The model layer | Make Gemma 4 turn messy speech into clean JSON, and make it degrade gracefully when it can't |
| **Lokesh Ullangula** | Data + the resolver | Make the numbers correct, and make the agent ask instead of guess |
| **Ayush Kumar Rai** | API + frontend + glue | Make it visible, and wire the pieces together |
| **Ayush Aditya** | Language + delivery | Make Kannada real, and make the submission complete |

Saket's half and Lokesh's half touch **no shared files**. Ayush Rai owns the only files that
import from both.

---

## T+0:00 → T+0:20 — everyone together, do not split up yet

On a call or shoulder to shoulder. This twenty minutes saves an hour later.

- [ ] Read `docs/api-contract.md` **out loud, together**. Fix anything wrong. Then freeze it.
- [ ] Everyone clones, everyone can reach `http://172.1.58.57:11434/api/tags`
- [ ] On the 4060: `OLLAMA_MAX_LOADED_MODELS=1`, confirm `ollama list` shows `gemma4:latest`
- [ ] First commit: this doc set + `LICENSE` + `.gitignore`, pushed
- [ ] Agree out loud on the cut list in `IMPLEMENTATION.md`, so cutting later is not a debate

---

## T+0:20 → T+0:35 — Saket, alone, everybody else waits on nothing

**The gate.** Three tests from `IMPLEMENTATION.md` § T+0:00 gate. Report the answers in
`PROGRESS.md` before writing any other code:

1. Does text extraction return correct JSON in en / hi / kn, with **names in Latin script**?
2. Does the audio path produce a usable transcript?
3. Is a round trip under ~4 s?

These three answers decide whether we build the voice demo and whether Kannada ships.
Everyone else starts their own work immediately — none of it depends on the answers.

---

## Saket — the model layer

Files: `llm.py`, `extract.py`, `rules.py`, `reply.py`

| Time | Task |
|---|---|
| T+0:20 | **The gate** (above). Post results to `PROGRESS.md`. |
| T+0:35 | `llm.py` — one `generate()` into Ollama. `temperature: 0`, `num_ctx: 4096`, `think: false`, `keep_alive: "30m"`, `stream: false`. Raise on failure; don't swallow. |
| T+1:00 | `extract.py` — the pinned JSON schema with the **unit enum**, and the prompt instruction to romanise names. Test against `tests/corpus.md` as Ayush Aditya fills it. |
| T+1:40 | `rules.py` — keyword fallback, English + Hindi only. Wire it as `extract()`'s except path, tagged `_source: "rule"`. **Do this before polishing extraction** — it's the safety net for everything after. |
| T+2:10 | `reply.py` — `confirm`, `ask_sku`, `ask_unit`, `not_understood`, in all three languages. Options carry `value`, and the text spells the choices out in words too. |
| T+2:40 | Help Ayush Rai integrate. Re-run the corpus end to end. |

**Your two traps:** an unconstrained `unit` field (the model will invent `"units"`), and
`gaya`/`gaye` read as a sale when `rate badh gaya` is a price change.

---

## Lokesh — data and the resolver

Files: `db.py`, `seed.py`, `units.py`, `inventory.py`, `reorder.py`, `resolver.py`

| Time | Task |
|---|---|
| T+0:20 | `db.py` — the six tables. Money columns are **integer paise**. |
| T+0:45 | `seed.py` — ~30 real kirana SKUs, starting aliases, and **14 days of sales history**. The history is not optional; the low-stock alert shows nothing without it. Add `--reset`. |
| T+1:15 | `units.py` — the three-language vocabulary and per-SKU conversions. `normalize_unit` returns `None` for unknown words — never pass them through. Bare `g` is **not** grams. |
| T+1:40 | `inventory.py` — `apply_movement` in **one connection, one commit**. Price converts by the same ratio as quantity. `stock_in` → `cost_per_unit`, `stock_out` → `sell_price`. `current_qty` floors at 0. |
| T+2:00 | `resolver.py` — exact alias, fuzzy, **near-tie → ask**, unknown → offer create. `learn_alias` only on human confirmation, never on a fuzzy auto-accept. **This is the highest-scoring file in the repo.** |
| T+2:40 | `reorder.py` — days of cover = `current_qty / avg_daily_sales`. Suggested order subtracts `current_qty`; don't recompute from scratch. |

**You can build and test `resolver.py` with fixtures, with no model running at all.** Don't
wait for Saket.

---

## Ayush Rai — API, frontend, glue

Files: `main.py`, `config.py`, `pipeline.py`, `routes/*`, `frontend/*`

| Time | Task |
|---|---|
| T+0:20 | `main.py`, `config.py`, and **stub routes** returning the fixed shapes from the contract. Push these early — they're what unblocks nothing-waiting-on-anything. |
| T+0:45 | `frontend/index.html` + `app.js` — WhatsApp-style chat. Green bubbles, right-aligned user, left-aligned bot, a phone frame. **Make it look real**; this is what a judge actually sees. |
| T+1:30 | Option buttons send `value` not `label`. In-flight guard so double-taps are no-ops. `escapeHtml` on everything from the API. `sender` from `sessionStorage`. Check `res.ok` before `res.json()`. |
| T+2:00 | `dashboard.html` + `dashboard.js` — stock table, low rows in red, two stat cards. |
| T+2:20 | `pipeline.py` — the orchestration. Pending row **cleared before parsing**. Intent gate. One shared `_apply_item()` for both paths. `run_in_threadpool` from the route. |
| T+3:00 | Swap stubs for the real pipeline. Integrate. |

**Your trap:** `pipeline.py` is where every subtle bug lives. Read that section of
`IMPLEMENTATION.md` twice before starting it.

---

## Ayush Aditya — language and delivery

Files: `tests/corpus.md`, `README.md`, screenshots, slides

| Time | Task |
|---|---|
| T+0:20 | `tests/corpus.md` — nine sentences: en/hi/kn × multi-item, ambiguous, query. **Find a Kannada speaker in the room if nobody on the team is one.** Saket is blocked on the Kannada rows. |
| T+0:50 | Verify the Kannada **unit vocabulary** with that speaker and hand corrections to Lokesh. A wrong unit word is what a local judge notices instantly. |
| T+1:20 | Judge Saket's Kannada extraction output. You are the only check on whether a transliteration is correct rather than merely plausible. |
| T+1:50 | `README.md` — what it does, how to run it, **the model and key dependencies**. This is a scored MLH deliverable, not paperwork. |
| T+2:30 | Demo script written out. Take the "before" dashboard screenshot while stock is still low. |
| T+3:00 | Screenshots of all four demo moments. Start the backup screen recording. |
| T+3:20 | Slides. Make sure every member can answer for their own area. |

**You are on the critical path twice** — the Kannada corpus blocks Saket, and nobody else
can judge Kannada correctness.

---

## T+3:00 → T+3:30 — everyone

- [ ] Full flow ten times, different phrasings, all three languages
- [ ] Ask-once verified end to end: ask → answer → **send the same message again** → silent
- [ ] A refusal verified: unrecognised unit writes **nothing**
- [ ] `python -m app.seed --reset`, then final screenshots on clean data
- [ ] Backup recording saved. Everything pushed.
- [ ] Pitch rehearsed twice, out loud

---

## Rules of engagement

1. **The contract is frozen at T+0:20.** After that, a field-name change gets announced to
   all three others before you push it.
2. **Nobody waits.** Stubs exist from T+0:45. Build against them.
3. **Stay in your own files.** If you need something changed in someone else's, ask them.
4. **Commit every ~30 minutes**, push every time. Small commits. Don't lose work.
5. **Update `PROGRESS.md` when you finish a chunk.** One line in the log. The next person —
   or the next AI session when context runs out — reads that file to pick up.
6. **Protect T+2:00 → T+2:45.** That's the resolver, and it's the highest-scoring work in
   the project. Don't let integration eat it.
7. **If you're behind at T+2:30, cut from the list.** Don't negotiate, don't extend. The
   order is already agreed.
