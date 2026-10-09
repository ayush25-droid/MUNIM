"""Shared route helpers: stub switch and the {"error": ...} body shape."""
import importlib.util

from .. import config


def use_stubs() -> bool:
    if config.USE_STUBS in ("1", "true", "yes"):
        return True
    if config.USE_STUBS in ("0", "false", "no"):
        return False
    return importlib.util.find_spec("app.pipeline") is None
