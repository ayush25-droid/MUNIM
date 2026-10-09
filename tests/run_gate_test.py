import base64
import json
import time
import requests
from PIL import Image
import io

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:latest"

PROMPT = """You are Munim, an automated bookkeeper reading kirana bills.
Examine this image carefully.

CRITICAL INSTRUCTIONS:
1. Determine if this image is a genuine retail/wholesale bill, receipt, cash memo, or handwritten order slip.
2. If the image is NOT a bill (e.g. photo of an object, desk, person, snack, furniture, wall) or is completely unreadable, output:
{"legible": false, "confidence": "low", "script": "latin", "raw_text": "", "lines": []}
Do NOT invent, imagine, or hallucinate any items.
3. If it IS a bill:
- Transcribe each line item into Latin script (lowercase), regardless of whether the original is in Kannada, Hindi, or English.
- Format each item in lines as: "<qty> <unit> <item name> <price_paise or price>"
- Extract plain numeric prices, omitting currency symbols.
- If lines are handwritten or partially obscured, skip what is unreadable and set "confidence": "low". Otherwise set "confidence": "high".
- "script" must be one of: "latin", "devanagari", "kannada", "mixed".

Output valid JSON only with keys:
- "legible": boolean
- "confidence": "high" or "low"
- "script": string
- "raw_text": string (full original transcription)
- "lines": list of strings (one cleaned item per line)
"""

def prepare_image(path):
    img = Image.open(path)
    # Ensure longest edge <= 1024
    w, h = img.size
    if max(w, h) > 1024:
        scale = 1024 / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def test_image(img_path):
    print(f"\n======================================")
    print(f"Testing {img_path}...")
    b64 = prepare_image(img_path)
    
    payload = {
        "model": MODEL,
        "prompt": PROMPT,
        "images": [b64],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_ctx": 4096
        },
        "keep_alive": "30m"
    }
    
    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=90)
    dur = time.time() - t0
    
    if resp.status_code != 200:
        print(f"FAILED with HTTP {resp.status_code}: {resp.text}")
        return {"error": resp.text, "duration": dur}
        
    data = resp.json()
    response_text = data.get("response", "")
    print(f"Duration: {dur:.2f}s")
    try:
        parsed = json.loads(response_text)
        print("Parsed response:")
        print(json.dumps(parsed, indent=2, ensure_ascii=True))
        return {"duration": dur, "parsed": parsed}
    except Exception as e:
        print("Raw response text (JSON parse error):", response_text.encode('ascii', errors='replace').decode('ascii'))
        return {"duration": dur, "raw": response_text}

if __name__ == "__main__":
    test_files = [
        "tests/bills/printed-01.jpg",
        "tests/bills/handwritten-01.jpg",
        "tests/bills/kannada-01.jpg",
        "tests/bills/not-a-bill.jpg"
    ]
    results = {}
    for f in test_files:
        results[f] = test_image(f)
