import json
import re
from pathlib import Path

from ..config import settings

FEATURES = {"device_info", "battery", "notifications", "selected_files"}


def _safe_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    return (value or "Android GPT Agent")[:80]


def create_project(app_name: str, server_url: str, features: dict[str, bool]) -> Path:
    safe_name = _safe_name(app_name)
    slug = "android_gpt_agent"
    out = settings.generated / slug
    out.mkdir(parents=True, exist_ok=True)
    enabled = {k: bool(features.get(k)) for k in FEATURES}
    (out / "android-gpt.json").write_text(
        json.dumps(
            {
                "app_name": safe_name,
                "server_url": server_url.rstrip("/"),
                "features": enabled,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out
