"""EXIF-rotate, downscale and re-encode a bill photo before it reaches the model.

This is the difference between a 4-second scan and a 40-second one (see the hardware
section of IMPLEMENTATION.md): a raw phone photo encodes to thousands of image tokens,
which blows the 4096-token context window and makes inference crawl. Write this before
ocr.py, and call it even though the browser already downscales client-side -- this is
the server-side guard.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError


class ImagePrepError(ValueError):
    """Raised when `raw` isn't a decodable image."""


def prepare(raw: bytes, max_edge: int = 1024) -> bytes:
    """EXIF-rotate, downscale so the longest edge is `max_edge`, convert to JPEG,
    strip metadata. Raises `ImagePrepError` on anything that isn't a decodable image.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImagePrepError(f"not a decodable image: {exc}") from exc

    # Phone photos are routinely sideways; this reads the orientation EXIF tag and
    # physically rotates the pixels to match, then drops the tag (and every other
    # metadata field) on re-encode below.
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    width, height = img.size
    longest = max(width, height)
    if longest > max_edge:
        scale = max_edge / longest
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        img = img.resize(new_size, Image.LANCZOS)

    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85)
    return out.getvalue()
