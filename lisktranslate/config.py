"""Saved regions and window options."""

from __future__ import annotations

import json
import os
from pathlib import Path


def config_path() -> Path:
    override = os.environ.get("LISKTRANSLATE_CONFIG")
    if override:
        path = Path(override)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    root = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(root) / "lisktranslate"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "config.json"


def load() -> dict:
    try:
        return json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save(data: dict) -> None:
    config_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
