# Test corpus

**Owner: Ayush Aditya.** Saket's gate is blocked on the first two bill photos — get those in
before anything else.

Put the photos in `tests/bills/` and record the expected result for each here, so passing or
failing is a fact rather than an opinion.

---

## The bills we need

| File | What it is | Why |
|---|---|---|
| `printed-01.jpg` | A clean printed supplier bill, 5–8 line items | The baseline. If this fails, escalate immediately. |
| `handwritten-01.jpg` | Handwritten on a pad, 5–8 items, realistic shorthand | **The headline risk.** Write one yourself if you can't find one. |
| `angle-01.jpg` | A bill shot at a bad angle | Phone photos are never square-on |
| `glare-01.jpg` | A bill with window glare across it | Shop lighting is bad |
| `crumpled-01.jpg` | A folded or crumpled bill | Bills live in pockets |
| `kannada-01.jpg` | A bill with Kannada item names | The transliteration path |
| `not-a-bill.jpg` | **Anything that isn't a bill** — a wall, a snack packet, a face | The hallucination guard. Matters as much as the rest. |

Writing the handwritten one yourself is fine and realistic — use pen and paper, 5–8 items,
real kirana names, and the abbreviations a supplier would actually use (`pkt`, `dzn`, `kg`,
`nos`). Don't print it neatly; that defeats the test.

---

## How to judge a scan

A bill passes only if **all** of these hold:

1. `legible: true`, and the line count matches the bill
2. Every `qty` is correct
3. Every `unit` is inside the enum (`packet` `box` `sack` `dozen` `kg` `gram` `litre` `piece`)
4. Every `name` comes back in **Latin script, lowercase**
5. Prices are correct, in **integer paise** (₹4.80 → `480`)
6. Items the catalogue genuinely can't distinguish come back `ambiguous`, **not** silently
   matched to one of them

`not-a-bill.jpg` passes only if `legible: false` and `items` is **empty**. Any invented line
item is a failure, no matter how plausible it looks.

---

## Expected results

Fill one of these in per bill, from the actual bill, before running the scan.

### `printed-01.jpg`

| Line | qty | unit | name | price (paise) | expect resolution |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

### `handwritten-01.jpg`

| Line | qty | unit | name | price (paise) | expect resolution |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

_(copy the block for each remaining bill)_

---

## Typed-text cases

The chat surface is secondary now, but it carries the multilingual demonstration and the
query path. Six cases.

| # | Message | Expect |
|---|---|---|
| en-1 | how much parle g is left | `query`, **0 items** |
| en-2 | twenty packets of parle-g came in | `stock_in`, 1 item |
| hi-1 | kitna parle g bacha hai | `query`, **0 items** |
| hi-2 | das maggi bik gaye | `stock_out`, 1 item — a real sale |
| hi-3 | 2 kg aata chahiye | **`query`** — "I *need* 2kg" parses as a clean item but must **not** write |
| kn-1 | _to be written by a Kannada speaker_ | `query`, 0 items |

`hi-3` is the important one. It's the case where a careless pipeline books stock from a
question.

---

## Unit vocabulary to verify

**Ayush Aditya: check the Kannada column with a native speaker and hand corrections to
Lokesh.** A wrong unit word is what a local judge notices instantly.

| Canonical | English / bill shorthand | Hindi | Kannada — VERIFY |
|---|---|---|---|
| `packet` | packet, pkt, pack | packet, pudiya | ಪ್ಯಾಕೆಟ್ (pyaket) |
| `box` | box, case, carton, ctn | peti, dabba | ಪೆಟ್ಟಿಗೆ (pettige), ಬಾಕ್ಸ್ (box) |
| `sack` | sack, bag, bdl | bori, katta | ಚೀಲ (cheela) |
| `dozen` | dozen, dzn, doz | darzan, dozen | ಡಜನ್ (dajan) |
| `kg` | kilo, kg, kilogram | kilo, kg | ಕೆಜಿ (keji), ಕಿಲೋ (kilo) |
| `gram` | gram, gm | gram, gm | ಗ್ರಾಂ (gram) |
| `litre` | litre, l, ltr, lt | litre | ಲೀಟರ್ (leetar) |
| `piece` | piece, pc, pcs, nos, no | nag, piece | ತುಂಡು (tundu) |

**Known collisions — don't break these:**

- Bare `g` must **not** map to grams. It eats `parle g` → `parle`. `gm` and `gram` are fine.
- `pav` stays a unit (0.25 kg) and must be removed from any bread alias.
- A stock-out needs an explicit sale verb (`bik`, `bech`, `nikla`, `sold`). The bare auxiliary
  `gaya`/`gaye` isn't enough — `rate badh gaya` is a price change, not a sale.

Printed bills bring their own: `nos` and `no` mean pieces, not a number; `bdl` is a bundle;
`ctn` is a carton. Expect to find at least one more during testing — finding it is part of
the job.

---

## Results

| Bill / case | Pass | Latency | Notes (paste the JSON on a failure) |
|---|---|---|---|
| printed-01 | | | |
| handwritten-01 | | | |
| angle-01 | | | |
| glare-01 | | | |
| crumpled-01 | | | |
| kannada-01 | | | |
| **not-a-bill** | | | must be `legible: false`, empty items |
| en-1 | | | |
| en-2 | | | |
| hi-1 | | | |
| hi-2 | | | |
| hi-3 | | | |
| kn-1 | | | |

**Decision rules:**

- `printed-01` failing is a project-level problem — stop and escalate, don't work around it.
- `handwritten-01` failing means demo printed bills only and disclose it on the slide. That's
  an acceptable outcome, not a defeat.
- `not-a-bill` hallucinating items is a demo-killer. Fix the prompt before building anything
  else on top.
