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

# When to translate: "all" = every message (default), "prefix" = only if message starts with TRANSLATE_PREFIX, "mention" = only if message @mentions the bot, "reaction" = only when someone adds REACTION_TRIGGER_EMOJI to a message
TRANSLATE_TRIGGER: str = os.environ.get("TRANSLATE_TRIGGER", "all").strip().lower() or "all"
# For trigger=prefix: only translate messages that start with this (e.g. "[translate]" or "#translate"). Prefix is stripped before translating.
TRANSLATE_PREFIX: str = os.environ.get("TRANSLATE_PREFIX", "[translate]").strip()
# For trigger=reaction: only translate when this emoji is added to a message. Use the shortcode name without colons (e.g. "de" for :de:, "globe" for :globe:).
REACTION_TRIGGER_EMOJI: str = os.environ.get("REACTION_TRIGGER_EMOJI", "de").strip().lower() or "de"

# Skip translation if the message contains any of these phrases (comma-separated, case-insensitive). E.g. exclude "translation request" meta-messages.
EXCLUDE_IF_CONTAINS: str = os.environ.get("EXCLUDE_IF_CONTAINS", "translation of the following,assist us with a translation").strip()
EXCLUDE_PHRASES_LIST: list[str] = [p.strip().lower() for p in EXCLUDE_IF_CONTAINS.split(",") if p.strip()]
