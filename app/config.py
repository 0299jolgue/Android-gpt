import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class Settings:
    port: int = int(os.getenv("PORT", "80"))
    host: str = os.getenv("HOST", "0.0.0.0")
    database: Path = ROOT / os.getenv("DATABASE_FILE", "data/android_gpt.db")
    templates: Path = ROOT / "templates"
    static: Path = ROOT / "static"
    generated: Path = ROOT / "generated"
    session_secret: str = os.getenv("SESSION_SECRET", "change-this-session-secret")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "change-me")

settings = Settings()
