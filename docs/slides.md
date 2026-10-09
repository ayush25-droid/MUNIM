# Munim — Presentation Slides Outline

## Slide 1: Title
- **Project**: Munim (मुनीम / ಮುನೀಮ್)
- **Subtitle**: Photograph a supplier bill. The inventory updates.
- **Track**: Track 2 — Best Open-Source AI Project (PS 03 — Real-World Operations)
- **Team**: Hold_The_Door
  - Ayush Aditya (Machine Host, Model QA, Test Corpus)
  - Ayush Kumar Rai (Vision, OCR Spine & Pipeline Orchestration)
  - Saket Kumar Gupta (FastAPI & Mobile Review UI)
  - Lokesh Ullangula (Data Model, Units & Resolution Engine)

---

## Slide 2: The Core Problem — Data Entry
- **13 Million Kirana Stores** in India — almost none use inventory software.
- Not a user experience failure: shopkeepers simply don't have the time to type 30 items after every delivery.
- The supplier bill is the **single physical moment** where inventory changes.
- Reading the bill costs the shopkeeper **one photo**.

---

## Slide 3: The Hard Part — Vernacular Shorthand & Silent Corruption
- Supplier shorthand is messy: `pkt`, `dzn`, `bori`, `ctn`, `nos`.
- Multilingual scripts: `Parle G`, `पारले जी`, `ಪಾರ್ಲೆ-ಜಿ`.
- Per-SKU conversions: A crate of soda $\neq$ a carton of biscuits.
- **The Core Danger**: Silent ledger corruption. Booking a wrong item doesn't crash the app; it quietly poisons financial books.
- **Design Rule**: When a guess would corrupt the books, **ask the shopkeeper**.

---

## Slide 4: System Architecture
```
   Phone Camera Photo (1024px)
               │
               ▼
   Gemma 4 (Local Vision OCR)  ──►  Transliterate to Latin plain text
               │
               ▼
   Extraction & Schema Enum   ──►  Enforce canonical units & integer paise
               │
               ▼
   Resolution Engine          ──►  Exact Alias / RapidFuzz / Near-Tie Guard
               │
               ▼
      [ HUMAN REVIEW UI ]     ──►  Scan is 100% Read-Only; no side effects
               │
         (User Confirms)
               │
               ▼
       Atomic Ledger Write    ──►  1 SQLite Transaction + Ask-Once Alias Learning
```

---

## Slide 5: The "Ask-Once" Memory Engine
- When an item is ambiguous (e.g., `maggi` matching both Noodles and Masala):
  1. Munim presents candidate options in a dropdown.
  2. Shopkeeper confirms the correct SKU.
  3. Munim registers the shorthand mapping in the `aliases` table.
- **Next time that bill arrives: zero friction.** It resolves silently.
- Munim gets quieter the longer the shop operates.

---

## Slide 6: Engineering Rigor on Edge Hardware
- Tested and running on an RTX 4060 Laptop (8 GB VRAM, 6.9 GB usable).
- **Single Model Footprint**: Gemma 4 (7.5B Q4_K_M) serves both vision OCR and text extraction.
- **Safe Context**: Capped at `num_ctx: 4096` to prevent KV-cache OOM.
- **Image Pre-processing**: EXIF orientation correction and client/server downscaling to 1024px.
- **Data Integrity**: Money represented exclusively in **integer paise**.

---

## Slide 7: Live Demo & Test Matrix
- **Printed Bill**: Clean 6-item wholesale invoice.
- **Handwritten Bill**: Realistic shorthand ballpoint memo parsed in **7.67 seconds**.
- **Kannada Bill**: Transliterated and matched to script-agnostic SKU inventory.
- **Hallucination Guard**: Non-bill photo rejected cleanly (`legible: false`, 0 items).
