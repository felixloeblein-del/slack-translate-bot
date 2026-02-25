"""
Slack Events API endpoint: on new channel message, translate EN -> DE and post as thread reply.
"""

import logging
import os
from collections import OrderedDict

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from . import config
from .slack_verify import verify_slack_request
from .translate import translate_en_to_de

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


def _already_processed(channel_id: str, ts: str) -> bool:
    key = (channel_id, ts)
    if key in _processed:
        return True
    _processed[key] = None
    while len(_processed) > _MAX_IDEMPOTENCY_SIZE:
        _processed.popitem(last=False)
    return False


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

    if not verify_slack_request(body, signature, timestamp):
        logger.warning("Slack request verification failed")
        return PlainTextResponse("Forbidden", status_code=403)

    try:
        import json
        data = json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.warning("Invalid JSON body: %s", e)
        return PlainTextResponse("Bad Request", status_code=400)

    # URL verification challenge (Slack sends this when you save the Request URL)
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        if challenge is not None:
            return JSONResponse(content={"challenge": challenge})
        return PlainTextResponse("Bad Request", status_code=400)

    # Event callback: acknowledge immediately (Slack expects 200 within 3s)
    if data.get("type") != "event_callback":
        return PlainTextResponse("OK", status_code=200)

    event = data.get("event") or {}
    if event.get("type") != "message":
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

    # Translate only when source is English
    translated = translate_en_to_de(text)
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
