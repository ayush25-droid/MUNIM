"""The single entry point into Ollama. Every other module that needs the model calls
`generate()` -- nobody else opens an HTTP connection to the inference box.

Owns the hard hardware limits from IMPLEMENTATION.md: num_ctx pinned at 4096, thinking
off, the model kept warm with keep_alive, and separate timeouts for text vs. vision
(a bill photo takes longer than a sentence).
"""
from __future__ import annotations

import json
import os

import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:latest")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "25"))
LLM_VISION_TIMEOUT = float(os.getenv("LLM_VISION_TIMEOUT", "40"))


class LLMError(RuntimeError):
    """Raised when Ollama can't be reached, times out, or returns something that
    doesn't parse. Callers are expected to catch this and fall through to a
    rule-based path -- an inference failure must never take down a request.
    """


def generate(
    prompt: str,
    schema: dict | None = None,
    images: list[bytes] | None = None,
    timeout: float | None = None,
) -> dict | str:
    """POST /api/generate on Ollama.

    Returns parsed JSON when `schema` is given (schema-constrained structured
    output), otherwise the raw response string. Raises `LLMError` on any
    failure -- never returns a half-parsed or partial result.

    `images` takes raw image bytes (already downscaled by `imageprep.prepare`);
    this function handles base64-encoding them for the request body.
    """
    if timeout is None:
        timeout = LLM_VISION_TIMEOUT if images else LLM_TIMEOUT

    payload: dict = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": {
            "temperature": 0,
            "num_ctx": OLLAMA_NUM_CTX,
        },
    }
    if schema is not None:
        payload["format"] = schema
    if images:
        import base64

        payload["images"] = [base64.b64encode(img).decode("ascii") for img in images]

    try:
        resp = httpx.post(
            f"{OLLAMA_HOST.rstrip('/')}/api/generate",
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        outer = resp.json()
    except httpx.HTTPError as exc:
        raise LLMError(f"ollama request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LLMError(f"ollama returned a non-JSON envelope: {exc}") from exc

    if "error" in outer:
        raise LLMError(f"ollama error: {outer['error']}")

    text = outer.get("response", "")
    if schema is None:
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model response did not match the requested schema: {exc}") from exc
