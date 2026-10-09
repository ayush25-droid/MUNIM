"""The single entry point into local speech-to-text, mirroring llm.py's role for
Ollama: everything that needs audio transcribed calls `transcribe()` here, nobody
else touches faster-whisper directly.

Runs faster-whisper (open-weight, Apache-2.0, CTranslate2 reimplementation of
OpenAI's Whisper) on CPU -- the 4060's one GPU slot is reserved for gemma4:latest
per IMPLEMENTATION.md's hardware limits ("never load a second model"), so
transcription never touches the GPU and never contends with a bill scan in flight.

Prototype feature on a branch -- PROGRESS.md's "Decisions made" table cut voice as
the primary input ("the bill is already in the shopkeeper's hand"), but typed chat
already exists as a secondary surface (/api/chat) for queries and corrections
without a camera. Voice plugs into that same surface: this module only produces the
text that extract.extract_message() already knows how to parse.
"""
from __future__ import annotations

import os
import subprocess

import numpy as np

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# faster-whisper's own audio decoder goes through PyAV, whose `av.open(...,
# metadata_errors=...)` call (faster_whisper/audio.py) was removed in PyAV 14+ --
# an upstream version mismatch, not something fixable from here. Decoding via an
# `ffmpeg` subprocess into raw PCM and handing WhisperModel.transcribe() a numpy
# array instead (a directly supported input type) sidesteps that broken path
# entirely, and ffmpeg is already a system dependency on this project regardless.
SAMPLE_RATE = 16000

# The three languages the frontend's picker offers -- a shopkeeper (or the demo's
# Kannada speaker) picks one before recording, same idea as choosing a keyboard
# before typing. Whisper's own language codes already line up with ours.
SUPPORTED_LANGUAGES = ("en", "hi", "kn")

_model = None


class VoiceError(RuntimeError):
    """Raised when audio can't be decoded or transcription otherwise fails. Callers
    are expected to map this to a 400, the same discipline routes/scan.py already
    applies to a bad image from imageprep.prepare.
    """


def transcribe(audio: bytes, language: str | None = None) -> dict:
    """Raw audio bytes (any format ffmpeg can decode -- webm/ogg/wav/m4a, whatever a
    browser's MediaRecorder produces) -> a transcript.

    Returns:
        {"text": str, "lang": str, "confidence": float}

    `language` (one of SUPPORTED_LANGUAGES) skips Whisper's own language-detection
    pass when given -- not just an accuracy nudge, but the single biggest latency
    win available here: a low-confidence auto-detect (seen on real Kannada audio
    during testing) made the "small" model's worst case 60-90s+ on this CPU, far
    outside the demo's latency budget. A human picking their own language up front
    is also just a reasonable UI, the same way a keyboard app asks once.

    Raises `VoiceError` on anything that fails to load the model, decode the audio,
    or produces no speech at all -- never returns an empty transcript silently.
    """
    pcm = _decode_to_pcm(audio)
    model = _get_model()
    forced = language if language in SUPPORTED_LANGUAGES else None
    try:
        segments, info = model.transcribe(pcm, language=forced, beam_size=1, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments).strip()
    except Exception as exc:  # noqa: BLE001 - inference failures all land here
        raise VoiceError(f"transcription failed: {exc}") from exc

    if not text:
        raise VoiceError("no speech detected in audio")

    return {
        "text": text,
        "lang": info.language,
        "confidence": round(float(info.language_probability), 2),
    }


def _decode_to_pcm(audio: bytes) -> np.ndarray:
    """Any browser/upload audio format -> 16kHz mono float32 PCM, via a system
    `ffmpeg` subprocess (format auto-detected from the byte stream itself).
    """
    try:
        proc = subprocess.run(
            ["ffmpeg", "-i", "pipe:0", "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"],
            input=audio,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise VoiceError("ffmpeg is not installed") from exc
    except subprocess.CalledProcessError as exc:
        raise VoiceError(f"could not decode audio: {exc.stderr.decode(errors='replace')[-300:]}") from exc

    pcm = np.frombuffer(proc.stdout, dtype=np.float32)
    if pcm.size == 0:
        raise VoiceError("decoded audio was empty")
    return pcm


def _get_model():
    """Loads once per process and stays resident -- a cold load is a few seconds,
    not worth paying on every request. CPU + int8 keeps this off the GPU entirely.
    """
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        try:
            _model = WhisperModel(WHISPER_MODEL_SIZE, device="cpu", compute_type=WHISPER_COMPUTE_TYPE)
        except Exception as exc:  # noqa: BLE001 - any load failure is a VoiceError
            raise VoiceError(f"failed to load whisper model {WHISPER_MODEL_SIZE!r}: {exc}") from exc
    return _model
