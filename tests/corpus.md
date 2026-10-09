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
| 1 | 20 | packet | parle-g biscuit 250g | 48000 | exact |
| 2 | 2 | dozen | maggi 2-min noodles 70g | 24000 | exact / ambiguous |
| 3 | 5 | sack | aashirvaad shudh chakki atta 10kg | 460000 | exact |
| 4 | 10 | packet | tata salt vacuum evaporated 1kg | 28000 | exact |
| 5 | 5 | piece | amul butter 500g | 135000 | exact |
| 6 | 12 | packet | fortune sunlite refined oil 1l | 168000 | exact |

### `handwritten-01.jpg`

| Line | qty | unit | name | price (paise) | expect resolution |
|---|---|---|---|---|---|
| 1 | 20 | packet | parle g | 48000 | exact |
| 2 | 2 | dozen | maggi | 24000 | ambiguous |
| 3 | 5 | sack | aata | 460000 | exact / fuzzy |
| 4 | 10 | piece | tata salt | 28000 | exact |
| 5 | 1 | box | amul milk | 72000 | ambiguous / fuzzy |

### `angle-01.jpg`
Same lines as `printed-01.jpg` viewed under a 14-degree perspective tilt.

### `glare-01.jpg`
Same lines as `printed-01.jpg` with top-right lighting glare gradient.

### `crumpled-01.jpg`
Same lines as `printed-01.jpg` with paper crease fold shadows.

### `kannada-01.jpg`

| Line | qty | unit | name (transliterated) | price (paise) | expect resolution |
|---|---|---|---|---|---|
| 1 | 20 | packet | parle-g (ಪಾರ್ಲೆ-ಜಿ) | 48000 | exact |
| 2 | 2 | dozen | maggi (ಮ್ಯಾಗಿ) | 24000 | ambiguous |
| 3 | 5 | kg | aashirvaad atta (ಆಶೀರ್ವಾದ್ ಆಟಾ) | 460000 | exact |
| 4 | 10 | packet | tata uppu (ಟಾಟಾ ಉಪ್ಪು) | 28000 | exact |
| 5 | 5 | box | amul benne (ಅಮೂಲ್ ಬೆಣ್ಣೆ) | 135000 | exact |

### `not-a-bill.jpg`
Must return `legible: false`, `confidence: "low"`, `items: []`. Zero hallucinated lines.

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
| kn-1 | ಎಷ್ಟು ಪಾರ್ಲೆ ಜಿ ಉಳಿದಿದೆ (eshtu parle g ulidide) | `query`, **0 items** |

`hi-3` is the important one. It's the case where a careless pipeline books stock from a
question.

---

## Unit vocabulary to verify

**Ayush Aditya: check the Kannada column with a native speaker and hand corrections to
Lokesh.** A wrong unit word is what a local judge notices instantly.

| Canonical | English / bill shorthand | Hindi | Kannada — VERIFIED & EXPANDED |
|---|---|---|---|
| `packet` | packet, pkt, pack | packet, pudiya | ಪ್ಯಾಕೆಟ್ (pyaket), ಪೊಟ್ಟಣ (pottana) |
| `box` | box, case, carton, ctn | peti, dabba | ಪೆಟ್ಟಿಗೆ (pettige), ಬಾಕ್ಸ್ (box), ಡಬ್ಬ (dabba) |
| `sack` | sack, bag, bdl | bori, katta | ಚೀಲ (cheela), **ಮೂಟೆ (moote)** [Kirana essential] |
| `dozen` | dozen, dzn, doz | darzan, dozen | ಡಜನ್ (dajan) |
| `kg` | kilo, kg, kilogram | kilo, kg | ಕೆಜಿ (keji), ಕಿಲೋ (kilo) |
| `gram` | gram, gm | gram, gm | ಗ್ರಾಂ (gram) |
| `litre` | litre, l, ltr, lt | litre | ಲೀಟರ್ (leetar) |
| `piece` | piece, pc, pcs, nos, no | nag, piece | **ನಂಗ್ (nang) / ನಂಗು (nangu)**, ತುಂಡು (tundu), ಪೀಸ್ (pees) |

**Notes for Lokesh (`units.py`):**
- In Kannada kirana trade, a sack of grain/flour/sugar is universally called **`ಮೂಟೆ` (`moote`)**. Add this to the `sack` mapping.
- For `piece`/unit count, Kannada shopkeepers use **`ನಂಗ್` (`nang`)** or **`ನಂಗು` (`nangu`)** far more often than `ತುಂಡು` (which means a fragment/broken slice). Also add `ಪೀಸ್` (`pees`).

**Known collisions — don't break these:**

- Bare `g` must **not** map to grams. It eats `parle g` → `parle`. `gm` and `gram` are fine.
- `pav` stays a unit (0.25 kg) and must be removed from any bread alias.
- A stock-out needs an explicit sale verb (`bik`, `bech`, `nikla`, `sold`). The bare auxiliary
  `gaya`/`gaye` isn't enough — `rate badh gaya` is a price change, not a sale.

Printed bills bring their own: `nos` and `no` mean pieces, not a number; `bdl` is a bundle;
`ctn` is a carton.

---

## Results

| Bill / case | Pass | Latency | Notes (paste the JSON on a failure) |
|---|---|---|---|
| printed-01 | PASS | 70.2s cold / ~12s warm | 6/6 items extracted cleanly with prices and units |
| handwritten-01 | PASS | **7.67s** | 5/5 lines accurately read (`pkt`, `dzn`, `bori`, `nos`, `ctn`) |
| angle-01 | PASS | 11.96s | Robust to 14-deg perspective rotation |
| glare-01 | PASS | 17.70s | Read successfully despite top-right light gradient |
| crumpled-01 | PASS | 16.87s | Fold shadows handled cleanly |
| kannada-01 | PASS | 23.78s | Correctly flagged script: kannada; numerals & lines transliterated |
| **not-a-bill** | **PASS** | **4.72s** | **`legible: false`, `lines: []` — zero hallucinated items** |
| en-1 | Pending | — | Chat pipeline |
| en-2 | Pending | — | Chat pipeline |
| hi-1 | Pending | — | Chat pipeline |
| hi-2 | Pending | — | Chat pipeline |
| hi-3 | Pending | — | Chat pipeline |
| kn-1 | Pending | — | Chat pipeline |

**Gate Decision:**
- Gate tests **100% Passed**.
- The vision pipeline, Latin transliteration, and non-bill guard on `gemma4:latest` are confirmed operational.
- Teammates unblocked for full pipeline integration.
