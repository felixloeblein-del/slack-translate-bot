"""Load configuration from environment. Do not commit .env (use .env.example as template)."""

import os
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env from project root (cwd) or package directory."""
    try:
        import dotenv
    except ImportError:
        return
    for base in (Path.cwd(), Path(__file__).resolve().parent):
        env_file = base / ".env"
        if env_file.is_file():
            dotenv.load_dotenv(env_file)
            break


_load_dotenv()


# Required
SLACK_SIGNING_SECRET: str = os.environ.get("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN: str = os.environ.get("SLACK_BOT_TOKEN", "")
DEEPL_API_KEY: str = os.environ.get("DEEPL_API_KEY", "")

# Optional: restrict to specific channel IDs (comma-separated). Empty = all channels the app is in.
SLACK_CHANNEL_IDS: str = os.environ.get("SLACK_CHANNEL_IDS", "")
# Parsed list (empty list = no filter = all channels)
CHANNEL_IDS_LIST: list[str] = [c.strip() for c in SLACK_CHANNEL_IDS.split(",") if c.strip()]

# Replay attack: reject requests older than this (seconds)
SLACK_REQUEST_MAX_AGE_SECONDS: int = int(os.environ.get("SLACK_REQUEST_MAX_AGE_SECONDS", "300"))

# When to translate: "all" = every message (default), "prefix" = only if message starts with TRANSLATE_PREFIX, "mention" = only if message @mentions the bot
TRANSLATE_TRIGGER: str = os.environ.get("TRANSLATE_TRIGGER", "all").strip().lower() or "all"
# For trigger=prefix: only translate messages that start with this (e.g. "[translate]" or "#translate"). Prefix is stripped before translating.
TRANSLATE_PREFIX: str = os.environ.get("TRANSLATE_PREFIX", "[translate]").strip()
