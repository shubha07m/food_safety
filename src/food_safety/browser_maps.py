"""Build-only public browser configuration. Never fall back to a server credential."""

import os
import re

from .storage import dump


def configured_key(root, name):
    if name in os.environ:
        return os.environ[name].strip()
    path = root / ".env"
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.removeprefix("export ").partition("=")
            if sep and key.strip() == name:
                return value.strip().strip("\"'")
    return ""


def browser_config(root):
    key = configured_key(root, "GOOGLE_MAPS_BROWSER_KEY")
    if key and not re.fullmatch(r"AIza[A-Za-z0-9_-]{35}", key):
        raise ValueError("invalid_browser_key_format")
    if key and key in {
        configured_key(root, "GOOGLE_MAPS_API_KEY"), configured_key(root, "GEMINI_API_KEY")
    }:
        raise ValueError("browser_key_must_be_separate_from_server_keys")
    return {"browser_key": key}


def build_browser_config(root):
    dump(root / "site/maps-config.json", browser_config(root))
