"""Application-owned settings locations; no E-Sys settings are imported."""

from __future__ import annotations

import json
import os
from pathlib import Path


def default_state_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "BMGARAGE"
    return Path(__file__).resolve().parent.parent / ".bmgarage"


def load_preferences(state_dir: Path | None = None) -> dict:
    try:
        path = Path(state_dir or default_state_dir()) / "gui-settings.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        selected = data.get("data_home")
        return {"data_home": selected} if selected is None or isinstance(selected, str) else {}
    except (OSError, ValueError):
        return {}
