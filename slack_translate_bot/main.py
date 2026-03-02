"""
Slack Events API endpoint: on new channel message, translate EN -> DE and post as thread reply.
"""

import logging
import os
import re
from collections import OrderedDict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from . import config
from .slack_verify import verify_slack_request
from .translate import translate_en_to_de

# Slack emoji shortcodes :name: — we replace with placeholders so DeepL doesn't translate them
_EMOJI_PATTERN = re.compile(r":([a-zA-Z0-9_+]+):")
_EMOJI_PLACEHOLDER = "EMOJISLACK"


def _replace_slack_emojis_for_translation(text: str) -> tuple[str, list[str]]:
    """Replace :shortcode: with placeholders. Returns (modified_text, list of original shortcodes in order)."""
    shortcodes: list[str] = []
    def repl(m: re.Match) -> str:
        shortcodes.append(":" + m.group(1) + ":")
        return f":{_EMOJI_PLACEHOLDER}{len(shortcodes)-1}:"
    return _EMOJI_PATTERN.sub(repl, text), shortcodes


def _restore_slack_emojis(text: str, shortcodes: list[str]) -> str:
    """Put original :shortcode: back in place of placeholders."""
    for i, orig in enumerate(shortcodes):
        text = text.replace(f":{_EMOJI_PLACEHOLDER}{i}:", orig)
    return text


def _split_headline_body(text: str) -> tuple[str, str]:
    """
    Split l10n-style content into headline (first line) and body (rest).
    Ensures DeepL translates them separately so the reply keeps two lines.
    """
    text = (text or "").strip()
    if not text:
        return ("", "")
    idx = text.find("\n")
    if idx < 0:
        return (text, "")
    headline = text[:idx].strip()
    body = text[idx + 1 :].strip()
    return (headline, body)


def _translate_headline_and_body(text: str) -> str | None:
    """
    Translate extracted content by splitting into headline and body, translating each
    separately, then rejoining with a newline so the reply keeps headline and body on separate lines.
    """
    if not text or not text.strip():
        return None
    text_for_deepl, emoji_shortcodes = _replace_slack_emojis_for_translation(text)
    headline, body = _split_headline_body(text_for_deepl)

    parts: list[str] = []
    if headline:
        t = translate_en_to_de(headline)
        parts.append(t if t else headline)
    if body:
        t = translate_en_to_de(body)
        parts.append(t if t else body)

    if not parts:
        return None
    translated = "\n".join(parts)
    return _restore_slack_emojis(translated, emoji_shortcodes)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Slack EN->DE Translate")

# Idempotency: avoid posting duplicate translations when Slack retries.
# In-memory (channel_id, ts) with bounded size; for multi-instance use Redis.
_MAX_IDEMPOTENCY_SIZE = 10_000
_processed: OrderedDict[tuple[str, str], None] = OrderedDict()

# Bot user ID for "mention" trigger (fetched once via auth.test)
_bot_user_id: str | None = None


def _get_bot_user_id() -> str | None:
    """Fetch our bot's user ID from Slack (for mention trigger). Cached after first call."""
    global _bot_user_id
    if _bot_user_id is not None:
        return _bot_user_id
    if not config.SLACK_BOT_TOKEN:
        return None
    try:
        import httpx
        r = httpx.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"},
            timeout=10.0,
        )
        if r.status_code == 200 and r.json().get("ok"):
            _bot_user_id = r.json().get("user_id")
            return _bot_user_id
    except Exception as e:
        logger.warning("auth.test failed: %s", e)
    return None


def _should_translate_and_strip(text: str) -> str | None:
    """
    If we should translate this message, return the text to send to DeepL (possibly stripped of prefix/mention).
    Otherwise return None.
    """
    trigger = config.TRANSLATE_TRIGGER
    if trigger == "all":
        return text
    if trigger == "prefix":
        prefix = config.TRANSLATE_PREFIX
        if not prefix or not text.startswith(prefix):
            return None
        stripped = text[len(prefix):].strip()
        return stripped if stripped else None
    if trigger == "mention":
        bot_id = _get_bot_user_id()
        if not bot_id:
            logger.warning("TRANSLATE_TRIGGER=mention but could not get bot user ID")
            return None
        mention = f"<@{bot_id}>"
        if mention not in text:
            return None
        # Remove the mention so we don't translate it; leave the rest
        stripped = text.replace(mention, " ", 1).strip()
        stripped = " ".join(stripped.split())  # collapse spaces
        return stripped if stripped else None
    return text


def _extract_content_to_translate(text: str) -> str:
    """
    If the message contains a known preamble phrase (e.g. 'translation of the following:'),
    return only the text after that phrase so we translate just the content, not the intro.
    Otherwise return the full text.
    """
    if not text or not config.EXTRACT_PHRASES_LIST:
        return text
    lower = text.lower()
    for phrase in config.EXTRACT_PHRASES_LIST:
        pos = lower.find(phrase.lower())
        if pos >= 0:
            after = text[pos + len(phrase) :].strip()
            if after:
                return after
    return text


def _already_processed(channel_id: str, ts: str) -> bool:
    key = (channel_id, ts)
    if key in _processed:
        return True
    _processed[key] = None
    while len(_processed) > _MAX_IDEMPOTENCY_SIZE:
        _processed.popitem(last=False)
    return False


def _fetch_message(
    channel_id: str, ts: str, thread_ts: str | None = None
) -> tuple[str | None, str | None]:
    """
    Fetch a single message by channel and ts.
    Returns (message_text, reply_thread_ts). reply_thread_ts is the thread_ts to use
    when posting the translation reply (parent message ts for threads, or message ts for channel messages).

    Tries conversations.history first (channel messages). If not found, uses
    conversations.replies with the reacted message ts directly. Slack accepts a
    thread parent ts or a reply ts for this method.
    """
    if not config.SLACK_BOT_TOKEN:
        return (None, None)
    try:
        import httpx
    except ImportError:
        return (None, None)
    try:
        # 1) Try channel history (works for top-level messages)
        r = httpx.post(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {config.SLACK_BOT_TOKEN}"},
            json={
                "channel": channel_id,
                "oldest": ts,
                "latest": ts,
                "inclusive": True,
                "limit": 1,
            },
            timeout=10.0,
        )
        j = r.json()
        if r.status_code == 200 and j.get("ok"):
            messages = j.get("messages") or []
            if messages:
                return ((messages[0].get("text") or "").strip(), ts)
            # ok=True but empty: try replies (reaction may be on thread reply; Slack doesn't send thread_ts)
            logger.info(
                "fetch_message: history empty for ts=%s, trying conversations.replies (reaction on thread reply)",
                ts,
            )
        elif r.status_code == 200 and not j.get("ok"):
            logger.warning(
                "fetch_message: conversations.history error channel=%s ts=%s error=%s",
                channel_id,
                ts,
                j.get("error", "unknown"),
            )

        # 2) Use conversations.replies directly with the reacted message ts.
        # This avoids expensive parent scanning and works for both parent and reply ts.
        ts_str = str(ts).strip()
        is_channel = channel_id.startswith(("C", "G"))
        replies_token = config.SLACK_USER_TOKEN or config.SLACK_BOT_TOKEN
        if is_channel and not config.SLACK_USER_TOKEN:
            logger.warning(
                "fetch_message: SLACK_USER_TOKEN is not set; conversations.replies on channel threads may fail"
            )

        def _fetch_via_replies(anchor_ts: str) -> tuple[str | None, str | None]:
            payload = {
                "channel": channel_id,
                "ts": anchor_ts,
                "oldest": ts_str,
                "latest": ts_str,
                "inclusive": True,
                "limit": 1,
            }
            r2 = httpx.post(
                "https://slack.com/api/conversations.replies",
                headers={"Authorization": f"Bearer {replies_token}"},
                json=payload,
                timeout=10.0,
            )
            if r2.status_code == 429:
                retry_after = getattr(r2, "headers", {}).get("Retry-After", "?")
                logger.warning(
                    "fetch_message: conversations.replies rate limited channel=%s ts=%s retry_after=%s",
                    channel_id,
                    anchor_ts,
                    retry_after,
                )
                return (None, None)
            j2 = r2.json()
            if r2.status_code != 200 or not j2.get("ok"):
                logger.warning(
                    "fetch_message: conversations.replies error channel=%s ts=%s error=%s",
                    channel_id,
                    anchor_ts,
                    j2.get("error", "unknown"),
                )
                return (None, None)
            messages = j2.get("messages") or []
            if not messages:
                return (None, None)
            msg = messages[0]
            text = (msg.get("text") or "").strip()
            post_thread_ts = msg.get("thread_ts") or msg.get("ts") or anchor_ts
            return (text, post_thread_ts)

        text, reply_thread_ts = _fetch_via_replies(ts_str)
        if text:
            return (text, reply_thread_ts)

        # If event provided parent ts, retry once with that parent anchor.
        if thread_ts:
            parent_ts = str(thread_ts).strip()
            if parent_ts and parent_ts != ts_str:
                text, reply_thread_ts = _fetch_via_replies(parent_ts)
                if text:
                    return (text, reply_thread_ts)

        logger.warning("fetch_message: unable to resolve message channel=%s ts=%s", channel_id, ts_str)
        return (None, None)
    except Exception as e:
        logger.warning("fetch_message failed: %s", e)
        return (None, None)


def _post_thread_reply(channel_id: str, thread_ts: str, text: str) -> bool:
    """Post message to Slack as a thread reply. Returns True on success."""
    if not config.SLACK_BOT_TOKEN:
        logger.warning("SLACK_BOT_TOKEN not set; cannot post reply")
        return False
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed; pip install httpx")
        return False
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {config.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "channel": channel_id,
        "thread_ts": thread_ts,
        "text": text,
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(url, headers=headers, json=payload)
        if r.status_code != 200:
            logger.error("Slack API error: %s %s", r.status_code, r.text)
            return False
        data = r.json()
        if not data.get("ok"):
            logger.error("Slack API not ok: %s", data)
            return False
        return True
    except Exception as e:
        logger.exception("Failed to post to Slack: %s", e)
        return False


@app.post("/slack/events")
async def slack_events(request: Request) -> Response:
    """
    Slack Events API endpoint. Verifies signature, handles url_verification challenge,
    and on message events translates EN->DE and posts as thread reply.
    """
    # Need raw body for signature verification (before parsing JSON)
    body = await request.body()
    signature = request.headers.get("x-slack-signature")
    timestamp = request.headers.get("x-slack-request-timestamp")

    try:
        import json
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.warning("Invalid JSON body: %s", e)
        return PlainTextResponse("Bad Request", status_code=400)

    # URL verification challenge: respond immediately so Slack can verify the URL.
    # (We do this before signature check so setup works even if env var isn't set yet.)
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        if challenge is not None:
            return JSONResponse(content={"challenge": challenge})
        return PlainTextResponse("Bad Request", status_code=400)

    # For all other requests, verify the signature
    if not verify_slack_request(body, signature, timestamp):
        logger.warning("Slack request verification failed")
        return PlainTextResponse("Forbidden", status_code=403)

    # Event callback: acknowledge immediately (Slack expects 200 within 3s)
    if data.get("type") != "event_callback":
        return PlainTextResponse("OK", status_code=200)

    event = data.get("event") or {}

    # --- Reaction trigger: translate only when someone adds the trigger emoji to a message ---
    if event.get("type") == "reaction_added":
        raw_reaction = event.get("reaction") or ""
        logger.info("reaction_added received: reaction=%r (expecting %r)", raw_reaction, config.REACTION_TRIGGER_EMOJI)
        if config.TRANSLATE_TRIGGER != "reaction":
            return PlainTextResponse("OK", status_code=200)
        reaction = raw_reaction.strip().lower().replace("-", "_")
        expected = config.REACTION_TRIGGER_EMOJI.lower().replace("-", "_")
        if reaction != expected:
            logger.info("reaction %r does not match trigger %r; skipping", reaction, expected)
            return PlainTextResponse("OK", status_code=200)
        item = event.get("item") or {}
        if item.get("type") != "message":
            return PlainTextResponse("OK", status_code=200)
        channel_id = item.get("channel")
        message_ts = item.get("ts")
        # thread_ts is set when the reacted message is a reply inside a thread (parent's ts)
        thread_ts = item.get("thread_ts")
        if not channel_id or not message_ts:
            return PlainTextResponse("OK", status_code=200)
        if config.CHANNEL_IDS_LIST and channel_id not in config.CHANNEL_IDS_LIST:
            return PlainTextResponse("OK", status_code=200)
        if _already_processed(channel_id, message_ts):
            return PlainTextResponse("OK", status_code=200)
        text, reply_thread_ts = _fetch_message(channel_id, message_ts, thread_ts=thread_ts)
        if not text:
            logger.warning(
                "reaction_added: could not fetch message channel=%s ts=%s (check fetch_message logs)",
                channel_id,
                message_ts,
            )
            return PlainTextResponse("OK", status_code=200)
        text = _extract_content_to_translate(text)
        if not text:
            return PlainTextResponse("OK", status_code=200)
        translated = _translate_headline_and_body(text)
        if not translated:
            return PlainTextResponse("OK", status_code=200)
        # reply_thread_ts from _fetch_message (parent ts for threads, or message ts for channel messages)
        if not reply_thread_ts:
            reply_thread_ts = message_ts
        if _post_thread_reply(channel_id, reply_thread_ts, translated):
            logger.info("Posted translation (reaction) for channel=%s ts=%s", channel_id, message_ts)
        return PlainTextResponse("OK", status_code=200)

    # --- Message trigger: translate on new message (all / prefix / mention) ---
    if event.get("type") != "message":
        return PlainTextResponse("OK", status_code=200)
    if config.TRANSLATE_TRIGGER == "reaction":
        return PlainTextResponse("OK", status_code=200)

    # Only process new user messages (no bot messages, no subtypes like channel_join)
    if event.get("bot_id") or event.get("subtype"):
        return PlainTextResponse("OK", status_code=200)

    channel_id = event.get("channel")
    ts = event.get("ts")
    text = (event.get("text") or "").strip()
    if not channel_id or not ts or not text:
        return PlainTextResponse("OK", status_code=200)

    # Optional filter: only translate in configured channel(s)
    if config.CHANNEL_IDS_LIST and channel_id not in config.CHANNEL_IDS_LIST:
        return PlainTextResponse("OK", status_code=200)

    # Idempotency
    if _already_processed(channel_id, ts):
        return PlainTextResponse("OK", status_code=200)

    # Only translate when trigger matches (all / prefix / mention)
    text_to_translate = _should_translate_and_strip(text)
    if text_to_translate is None:
        return PlainTextResponse("OK", status_code=200)
    text_to_translate = _extract_content_to_translate(text_to_translate)
    if not text_to_translate:
        return PlainTextResponse("OK", status_code=200)

    # Translate headline and body separately so the reply keeps them on two lines
    translated = _translate_headline_and_body(text_to_translate)
    if not translated:
        return PlainTextResponse("OK", status_code=200)

    # Post as thread reply
    if _post_thread_reply(channel_id, ts, translated):
        logger.info("Posted translation for channel=%s ts=%s", channel_id, ts)
    else:
        logger.error("Failed to post translation for channel=%s ts=%s", channel_id, ts)

    return PlainTextResponse("OK", status_code=200)


@app.get("/health")
async def health() -> dict:
    """Health check for hosting platforms."""
    return {"status": "ok"}


def run() -> None:
    """Run the server (e.g. for local development)."""
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    run()
