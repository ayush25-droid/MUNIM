# Test corpus

**Owner: Ayush Aditya.** Saket is blocked on the Kannada rows — fill those first.

Nine cases: three languages × three sentence types. Every one of them is a real failure mode
we've either hit or expect.

## How to judge a result

A case passes only if **all four** hold:

1. `intent` is correct
2. the item count is correct
3. every `unit` is inside the enum (`packet` `box` `sack` `dozen` `kg` `gram` `litre` `piece`)
4. every `name` comes back in **Latin script, lowercase**

Query rows additionally must return an **empty `items` array**. A question must never move
stock — if a query extracts items, that's a failure even if the items are right.

---

## English

| # | Sentence | Expect |
|---|---|---|
| en-1 | twenty packets of Parle-G came in today, and five kilos of atta at forty-six rupees | `stock_in`, 2 items, atta price 4600 paise |
| en-2 | two amul came in | `stock_in`, 1 item → resolver must say **ambiguous** |
| en-3 | how much parle g is left | `query`, **0 items** |

## Hindi

| # | Sentence | Expect |
|---|---|---|
| hi-1 | aaj bees Parle-G aaye, aur paanch kilo aata, aata ka rate badh gaya - chhiyalis rupaye | `stock_in`, 2 items. **Not** a sale — `gaya` here is a price change |
| hi-2 | do amul aaye | `stock_in`, 1 item → **ambiguous** |
| hi-3 | kitna parle g bacha hai | `query`, **0 items** |

## Kannada — TO BE WRITTEN

Replace these with sentences from a Kannada speaker. Write each in **both** Kannada script
and romanised form, so we can test whether the model handles both.

| # | Sentence (Kannada script) | Romanised | Expect |
|---|---|---|---|
| kn-1 | _multi-item + price_ | | `stock_in`, 2 items |
| kn-2 | _ambiguous item_ | | `stock_in`, 1 item → **ambiguous** |
| kn-3 | _a stock question_ | | `query`, **0 items** |

Rough shape to ask for, so the speaker knows what's needed:

- **kn-1** — "today twenty Parle-G came in, and five kilos of rice"
- **kn-2** — "two amul came in" (deliberately ambiguous — butter or milk?)
- **kn-3** — "how much Parle-G is left?"

---

## Extra cases worth running once the nine pass

| Sentence | Why |
|---|---|
| das maggi bik gaye | A real sale. Must be `stock_out`, not `stock_in`. |
| do peti coke aaye | Unit conversion — 2 box → 48 pieces on a 24-per-box SKU |
| 2 kg aata chahiye | "I *need* 2kg" — parses as a clean item but is a **query**. Must not write. |
| teen dabba biscuit aaye | `dabba` → `box`. Tests the Hindi unit vocabulary. |
| (empty message) | Must not crash, must not match the first candidate |
| sku:abc | Must not crash — treated as "not an answer" |

---

## Unit vocabulary to verify

**Ayush Aditya: check the Kannada column with a native speaker and hand corrections to
Lokesh.** A wrong unit word is what a local judge notices instantly.

| Canonical | English | Hindi | Kannada — VERIFY |
|---|---|---|---|
| `packet` | packet, pkt, pack | packet, pudiya | ಪ್ಯಾಕೆಟ್ (pyaket) |
| `box` | box, case, carton | peti, dabba | ಪೆಟ್ಟಿಗೆ (pettige), ಬಾಕ್ಸ್ (box) |
| `sack` | sack, bag | bori, katta | ಚೀಲ (cheela) |
| `dozen` | dozen | darzan, dozen | ಡಜನ್ (dajan) |
| `kg` | kilo, kg, kilogram | kilo, kg | ಕೆಜಿ (keji), ಕಿಲೋ (kilo) |
| `gram` | gram, gm | gram, gm | ಗ್ರಾಂ (gram) |
| `litre` | litre, l, ltr | litre | ಲೀಟರ್ (leetar) |
| `piece` | piece, pc, nos | nag, piece | ತುಂಡು (tundu) |

**Known collisions — do not break these:**

- Bare `g` must **not** map to grams. It eats `parle g` → `parle`. `gm` and `gram` are fine.
- `pav` stays a unit (0.25 kg) and must be removed from any bread alias.
- A stock-out needs an explicit sale verb (`bik`, `bech`, `nikla`, `sold`). The bare
  auxiliary `gaya`/`gaye` is not enough — `rate badh gaya` is a price change.

Expect Kannada to have its own equivalents of at least one of these. Finding it is part
of the job.

---

## Results

Fill in as tests run. Paste the actual JSON for any failure.

| Case | Pass | Latency | Notes |
|---|---|---|---|
| en-1 | | | |
| en-2 | | | |
| en-3 | | | |
| hi-1 | | | |
| hi-2 | | | |
| hi-3 | | | |
| kn-1 | | | |
| kn-2 | | | |
| kn-3 | | | |

**Decision rule:** if fewer than 6 of 9 pass, `rules.py` becomes the primary extraction path
and the model becomes the assist. That still satisfies the track — say so plainly on the
slide rather than hiding it.
