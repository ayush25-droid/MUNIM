"""Environment config and logging. Values come from backend/.env (see ../.env.example)."""
import logging
import os
from pathlib import Path


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.split(" #")[0].strip())


_load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:latest")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "25"))
LLM_VISION_TIMEOUT = float(os.getenv("LLM_VISION_TIMEOUT", "40"))
IMAGE_MAX_EDGE = int(os.getenv("IMAGE_MAX_EDGE", "1024"))
DB_PATH = os.getenv("DB_PATH", "munim.db")
DEMO_SHOP_ID = int(os.getenv("DEMO_SHOP_ID", "1"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "15")) * 1024 * 1024
# Serve canned contract fixtures instead of the real pipeline. Auto-off once pipeline.py exists.
USE_STUBS = os.getenv("USE_STUBS", "auto").lower()


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return logging.getLogger(name)
