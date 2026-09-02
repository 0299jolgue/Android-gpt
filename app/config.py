import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


_cfg = _load_config()
_server = _cfg.get("server", {})
_paths = _cfg.get("paths", {})
_logging = _cfg.get("logging", {})
_auth = _cfg.get("auth", {})


@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", _server.get("port", 80)))
    host: str = os.getenv("HOST", _server.get("host", "0.0.0.0"))
    database: Path = ROOT / os.getenv("DATABASE_FILE", _cfg.get("database", "data/android_gpt.db"))
    templates: Path = ROOT / _paths.get("templates", "templates")
    static: Path = ROOT / _paths.get("static", "static")
    generated: Path = ROOT / _paths.get("generated", "generated")
    logs: Path = ROOT / _paths.get("logs", "data/logs/app.log")
    log_level: str = os.getenv("LOG_LEVEL", _logging.get("level", "INFO"))
    session_secret: str = os.getenv("SESSION_SECRET", "change-this-session-secret")
    admin_username: str = os.getenv("ADMIN_USERNAME", _auth.get("admin_username", "admin"))
    admin_password: str = os.getenv("ADMIN_PASSWORD", "change-me")
    allowed_commands: tuple = tuple(_cfg.get("android", {}).get("allowed_commands", ["ping", "refresh", "notify"]))


settings = Settings()
