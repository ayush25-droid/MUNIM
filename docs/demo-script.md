# Munim — Demo Script & Presentation Guide
**Presenter / Host**: Ayush Aditya
**Audience**: Hacktoberfest Bengaluru '26 Judges & Developers (Track 2 — Best Open-Source AI Project)
**Target Duration**: 3 minutes + 2 minutes Q&A

---

## 1. The Opening Hook (0:00 – 0:30)
> *"There are 13 million kirana stores in India. Almost none of them track inventory with software.*
> *This isn't a UX failure or tech illiteracy. A shopkeeper has customers at the counter, deliveries at the door, and one pair of hands. Typing thirty SKUs into an app is a task for which time simply does not exist.*
> *Data entry is where every kirana software product dies.*
> 
> *But there is one moment where data already exists physically: the supplier bill in their hand. Reading that bill costs exactly one photo. That is what Munim does."*

---

## 2. Live Demo — Step 1: Scanning a Handwritten Bill (0:30 – 1:15)
- **Action**: Open web app on phone / browser (`http://localhost:5500` or local network IP).
- **Action**: Tap camera / upload `tests/bills/handwritten-01.jpg` (written on a pad with blue ballpoint pen, shorthand units like `pkt`, `dzn`, `bori`, `nos`, `ctn`).
- **Talking Point**:
  > *"Notice what happens. In under 8 seconds, our open-weight model Gemma 4 transcribes the handwriting and extracts the lines.*
  > *Look at the Review Table. Notice that NOTHING has been written to the inventory ledger yet. Scan is completely read-only.*
  > *Why? Because committing misread handwritten rows corrupts books silently. A good agent knows the difference between confidence and certainty."*

---

## 3. Live Demo — Step 2: The Ambiguity Gate & Ask-Once Learning (1:15 – 2:00)
- **Show**:
  - `20 pkt parle g 480` $\rightarrow$ Green tick (**exact** match: Parle-G Biscuit)
  - `2 dzn maggi 240` $\rightarrow$ Amber dropdown (**ambiguous**: Maggi Noodles vs Maggi Masala)
- **Talking Point**:
  > *"Look at line 2: 'Maggi'. The fuzzy matcher scored ~90 against both Maggi Noodles and Maggi Masala. Rather than flipping a coin and corrupting the stock, Munim halts and asks.*
  > *I select 'Maggi Noodles 70g' from the dropdown and hit Confirm."*
- **Action**: Click **Confirm**. Show the success toast and `aliases_learned`: `[{"text": "maggi", "sku_id": 11}]`.
- **The Punchline**:
  > *"Munim wrote to the alias table. Watch what happens if I re-scan that bill..."*
  *(Re-upload)*
  > *"Now Maggi resolves automatically without asking. It asks once and never again. Munim gets quieter the longer the shopkeeper uses it."*

---

## 4. Live Demo — Step 3: Multilingual & Hallucination Guard (2:00 – 2:40)
- **Multilingual Demonstration**:
  - Upload `tests/bills/kannada-01.jpg`.
  - **Talking Point**:
    > *"Here is a bill written in Kannada script: 'ಪಾರ್ಲೆ-ಜಿ' (Parle-G) and 'ಆಶೀರ್ವಾದ್ ಆಟಾ'.*
    > *During OCR, Munim transliterates the text into Latin script. That means our resolver, alias database, and unit matching are 100% script-agnostic. One single alias row covers Kannada, Hindi, and English simultaneously without heavy multi-lingual embeddings."*
- **Hallucination Guard**:
  - Upload `tests/bills/not-a-bill.jpg` (photo of a desk/laptop monitor).
  - **Result**: Immediate refusal (`legible: false`, 0 items).
  - **Talking Point**:
    > *"A common trap with vision LLMs is inventing deliveries from random photos. If a shopkeeper takes a photo of their desk or the photo is blurred, Munim refuses it cleanly. Zero hallucinated items."*

---

## 5. Technical Architecture & Constraints (2:40 – 3:00)
- **Slide / Verbal Summary**:
  - **Single Open-Weight Model**: `gemma4:latest` (7.5B Q4_K_M) hosted entirely locally on Ollama on an RTX 4060 Laptop (6.9 GB VRAM).
  - **Hardware Safeguards**: Context locked to 4096 tokens, images strictly downscaled to 1024px before inference, single loaded model (`OLLAMA_MAX_LOADED_MODELS=1`).
  - **Financial Rigor**: All money stored and passed in integer paise (₹4.80 $\rightarrow$ `480`), atomic single-transaction ledger commits with 409 idempotency guards against double-taps.

---

## 6. Judge Q&A Cheat Sheet

| Question | Answer |
|---|---|
| **"Why not use WhatsApp instead of a web app?"** | Twilio trial accounts restrict outbound template messages, require sandbox approvals, and eat critical judging hours. A mobile-responsive web app with `<input type="file" capture="environment">` provides the exact same 1-tap camera UX with zero third-party dependencies. |
| **"Why plain text OCR before structured JSON?"** | If an LLM tries to emit end-to-end JSON from an image in one shot, an obscure handwriting format breaks the whole JSON parser. By flattening to plain text first: (1) rule-based regex extractors serve as reliable fallbacks, (2) the intermediate transcript is displayed and editable by the shopkeeper, and (3) typed chat queries share the exact same resolution pipeline. |
| **"Why RapidFuzz instead of Vector Embeddings?"** | Kirana SKU names are short shorthand terms (`parle g`, `atta 5kg`). Embeddings hallucinate semantic equivalence between unrelated brands and require extra VRAM and vector libraries. RapidFuzz with a tuned ratio + near-tie penalty is deterministic, runs in under 1ms, and uses zero GPU memory. |
| **"What happens if handwriting is truly unreadable?"** | Munim sets `confidence: "low"` and flags uncertain rows in the UI, requiring explicit user verification before confirmation. |
