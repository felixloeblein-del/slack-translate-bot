# Slack Translate Bot (EN -> DE)

FastAPI Slack Events bot that translates English messages to German with DeepL and posts the translation as a thread reply.

## Latest Updates (2026-03-02)

- Fixed reaction-triggered translation for messages inside threads.
  - Uses robust `conversations.history` + `conversations.replies` lookup flow.
  - Uses Slack-compatible API limits (`limit=15`) for history/replies calls.
  - Uses form-encoded Slack Web API requests and retries `invalid_arguments` with GET params.
  - Uses `SLACK_USER_TOKEN` for channel thread reads (required by Slack for many channel thread cases).
- Added reaction-mode edit handling (`message_changed`).
  - If a message with trigger emoji is edited, bot posts an updated translation reply.
  - If edit payload does not include reactions, bot checks current reactions via `reactions.get`.
  - Slack retry duplicates are deduped per `(message_ts + edit_ts)`.

## Features

- Translation EN -> DE with DeepL
- Trigger modes:
  - `all`
  - `prefix`
  - `mention`
  - `reaction` (recommended for this project)
- Preamble stripping (`EXTRACT_CONTENT_AFTER`)
- Slack emoji shortcode preservation (`:emoji_name:`)
- Thread-safe behavior for:
  - top-level messages
  - thread replies
  - edited messages in reaction mode

## Requirements

- Python 3.11+
- Slack app with Events API enabled
- DeepL API key

Install:

```bash
pip install -r requirements.txt
```

Run locally:

```bash
uvicorn slack_translate_bot.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## Environment Variables

Copy `.env.example` to `.env` and set values:

- Required:
  - `SLACK_SIGNING_SECRET`
  - `SLACK_BOT_TOKEN`
  - `DEEPL_API_KEY`
- Optional:
  - `TRANSLATE_TRIGGER` (`all|prefix|mention|reaction`)
  - `REACTION_TRIGGER_EMOJI` (default `de`)
  - `SLACK_CHANNEL_IDS` (comma-separated channel IDs)
  - `SLACK_USER_TOKEN` (xoxp, strongly recommended for channel thread replies)
  - `EXTRACT_CONTENT_AFTER`

## Slack App Setup

### Event Subscriptions

Set Request URL to:

`https://<your-service>/slack/events`

Subscribe to bot events:

- `reaction_added` (for reaction trigger)
- `message.channels` (needed for message edits in public channels)
- `message.groups` (needed if you use private channels)

### OAuth Scopes

Bot token scopes:

- `chat:write`
- `channels:read`
- `channels:history`
- `reactions:read`
- `groups:history` (if private channels)

User token scopes (for `SLACK_USER_TOKEN`, recommended):

- `channels:history`
- `groups:history` (if private channels)

After scope/event changes, reinstall the Slack app.

## Behavior Notes

### Reaction mode (`TRANSLATE_TRIGGER=reaction`)

- Add `:de:` to a message -> bot posts translation as thread reply.
- Works for:
  - top-level channel posts
  - replies inside threads

### Edited message behavior (reaction mode)

- If edited message still has trigger emoji -> bot posts updated translation reply.
- If trigger emoji is not present -> edit is ignored.

### Re-adding same emoji

- In same app runtime, duplicate `reaction_added` on same message `ts` is ignored by idempotency cache.
- After restart/deploy (cache reset), re-adding can translate again.

## Testing

Run all tests:

```bash
PYTHONPATH=. pytest -q
```

Current suite covers:

- message fetch (history/replies + fallbacks)
- translation utilities
- extraction logic
- reaction-mode edit flow

## Deploy (Render)

This repo includes `render.yaml` for Web Service deployment.

Default start command:

```bash
uvicorn slack_translate_bot.main:app --host 0.0.0.0 --port $PORT
```

## Troubleshooting

- `reaction_added` seen but no translation:
  - verify emoji name matches `REACTION_TRIGGER_EMOJI`
  - verify app is in the channel
  - verify event subscription includes `reaction_added`
- Thread replies fail to fetch:
  - set `SLACK_USER_TOKEN` (xoxp)
  - verify user token scopes (`channels:history` and `groups:history` if needed)
- Edit translations not firing:
  - verify `message.channels` (and `message.groups` for private) is subscribed
  - check logs for `message_changed received for reaction mode`
