# Slack auto-translate (English → German)

Standalone HTTP service that subscribes to Slack Events API and automatically translates English channel messages to German, posting the translation as a **thread reply** under the original message.

This project lives under `Documents/Repo Destination/slack-translate-bot` and is independent of any other repo.

## How it works

1. You create a Slack app, enable Event Subscriptions, and set the Request URL to `https://your-host/slack/events`.
2. When someone posts a message in a channel where the app is installed, Slack sends an HTTP POST to this endpoint.
3. The service verifies the request signature, translates the message with DeepL (only when the detected source language is English), and posts the German translation as a thread reply.

## Setup

### 1. Slack app

1. Create an app at [api.slack.com/apps](https://api.slack.com/apps).
2. **Event Subscriptions**: Enable, set Request URL to your deployed URL (e.g. `https://your-domain.com/slack/events`). Subscribe to **message.channels** (or use a channel filter).
3. **OAuth & Permissions**: Add Bot Token Scopes: `channels:history`, `channels:read`, `chat:write`.
4. Install the app to your workspace and **invite the bot to the channel(s)** you want to translate.
5. Copy **Signing Secret** (Basic Information) and **Bot User OAuth Token** (OAuth & Permissions) into `.env`.

### 2. DeepL

1. Get an API key from [DeepL for Developers](https://www.deepl.com/pro-api).
2. Set `DEEPL_API_KEY` in `.env`.

### 3. Environment

From the **slack-translate-bot** directory:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Set:

- `SLACK_SIGNING_SECRET` – from Slack app Basic Information
- `SLACK_BOT_TOKEN` – Bot User OAuth Token (starts with `xoxb-`)
- `DEEPL_API_KEY` – your DeepL API key

Optional:

- `SLACK_CHANNEL_IDS` – comma-separated channel IDs; if set, only these channels are translated (default: all channels the bot is in).

### 4. Run locally

From the **slack-translate-bot** directory:

```bash
pip install -r requirements.txt
python -m slack_translate_bot.main
```

Or with uvicorn:

```bash
uvicorn slack_translate_bot.main:app --host 0.0.0.0 --port 8000
```

**Why ngrok?** Slack’s servers send HTTP POSTs *to* your app when someone posts a message. Your app must be reachable at a **public HTTPS URL**. When you run the app on your laptop (`localhost`), the internet can’t reach it. Ngrok creates a temporary tunnel: a public URL (e.g. `https://abc.ngrok.io`) forwards to your `localhost:8000`. So ngrok is only for **local testing**. When your computer or the app is off, the URL stops working.

**If you need the bot always on (even when your computer is off):** don’t use ngrok. Deploy the app to a cloud host (see **Deploy for 24/7** below) and use that URL as the Slack Request URL.

### 5. Deploy for free (Render) – recommended first

**Free tier:** Render’s free web service tier doesn’t require a credit card. The service may spin down after ~15 minutes of no traffic and take ~30–60 seconds to wake on the first message; after that, translations work as normal.

1. **Put the project on GitHub**
   - Create a new repo on GitHub (e.g. `slack-translate-bot`).
   - In Terminal, from the project folder:
     ```bash
     cd "/Users/felix.loeblein/Documents/Repo Destination/slack-translate-bot"
     git init
     git add .
     git commit -m "Initial commit"
     git branch -M main
     git remote add origin https://github.com/YOUR-USERNAME/slack-translate-bot.git
     git push -u origin main
     ```
   - (Replace `YOUR-USERNAME` with your GitHub username.)

2. **Create the Slack app and get secrets (so you can add them on Render)**
   - [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch** (e.g. “EN→DE Translate”).
   - **OAuth & Permissions** → Bot Token Scopes: `channels:history`, `channels:read`, `chat:write` → **Install to Workspace**.
   - Copy **Signing Secret** (Basic Information) and **Bot User OAuth Token** (OAuth & Permissions). You’ll paste these into Render in step 4.
   - Don’t set Event Subscriptions or Request URL yet; do that after you have the Render URL.

3. **Deploy on Render**
   - Go to [render.com](https://render.com) and sign up / log in (GitHub login is easiest).
   - **Dashboard** → **New +** → **Web Service**.
   - **Connect a repository**: select your GitHub account and the `slack-translate-bot` repo. Click **Connect**.
   - Render may auto-fill from `render.yaml`. If not, set:
     - **Build command:** `pip install -r requirements.txt`
     - **Start command:** `uvicorn slack_translate_bot.main:app --host 0.0.0.0 --port $PORT`
   - **Instance type:** leave **Free**.
   - Click **Advanced** → **Add Environment Variable**. Add:
     - `SLACK_SIGNING_SECRET` = (paste Signing Secret)
     - `SLACK_BOT_TOKEN` = (paste Bot User OAuth Token)
     - `DEEPL_API_KEY` = (your DeepL API key)
   - Click **Create Web Service**. Wait for the first deploy to finish.

4. **Get your URL**
   - At the top of the service page you’ll see a URL like `https://slack-translate-bot-xxxx.onrender.com`. That’s your **translation bot URL**.
   - The **Request URL** for Slack is: `https://slack-translate-bot-xxxx.onrender.com/slack/events` (your URL + `/slack/events`).

5. **Point Slack at the bot**
   - In [api.slack.com/apps](https://api.slack.com/apps) → your app → **Event Subscriptions** → **On**.
   - **Request URL:** paste `https://YOUR-RENDER-URL/slack/events` → **Save**. It should show **Verified**.
   - Under **Subscribe to bot events**, add **message.channels** → **Save Changes**.

6. **Test**
   - In a Slack channel: `/invite @EN→DE Translate` (or your app name), then post an English message. The bot should reply in a thread with the German translation.

---

**Other free options**

- **Railway:** [railway.app](https://railway.app) – free plan available; deploy from the same GitHub repo (Railway can use the `Dockerfile` in this repo). Add the same env vars in the project **Variables**, then use the generated URL + `/slack/events` as the Slack Request URL.
- **Fly.io:** Free allowance; use `fly launch` and set env vars; then use `https://your-app.fly.dev/slack/events` as the Request URL.

After deployment, the bot runs on the host; you don’t need your computer or ngrok.

## Try it and test it

### Quick test flow

1. **Install and configure**
   ```bash
   cd "/Users/felix.loeblein/Documents/Repo Destination/slack-translate-bot"
   pip install -r requirements.txt
   cp .env.example .env
   ```
   Edit `.env` and add (you’ll fill Slack values in step 4):
   - `DEEPL_API_KEY` – get a free key at [DeepL API](https://www.deepl.com/pro-api#developer)

2. **Run the app**
   ```bash
   python -m slack_translate_bot.main
   ```
   You should see the app listening on port 8000.

3. **Expose it with ngrok (only for local testing – not for 24/7)**  
   In another terminal: `ngrok http 8000`. Copy the **HTTPS** URL and use `https://YOUR-NGROK-URL/slack/events` as the Slack Request URL. For always-on, use **Deploy for 24/7** above instead.

4. **Create and configure the Slack app**
   - Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch** (name e.g. “EN→DE Translate”).
   - **Event Subscriptions** → Turn **On**.
   - **Request URL**: `https://YOUR-NGROK-URL/slack/events` (e.g. `https://abc123.ngrok.io/slack/events`).  
     Slack will send a challenge; if your app is running, it should verify and show “Verified”.
   - Under **Subscribe to bot events**, add **message.channels** (or **message.channels** with a channel filter if you want only one channel).
   - **OAuth & Permissions** → **Bot Token Scopes**: add `channels:history`, `channels:read`, `chat:write`.
   - **Install App** to your workspace.
   - Copy **Signing Secret** (under **Basic Information**) and **Bot User OAuth Token** (under **OAuth & Permissions**) into your `.env` as `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN`.
   - Restart the app so it picks up the new env vars.

5. **Invite the bot and test**
   - In Slack, open the channel where you want translations.
   - Invite the app: type `/invite @YourAppName` (the name you gave the app) in that channel.
   - Post a message in **English**, e.g. “Hello, how are you?”  
   - Within a few seconds you should see a **thread reply** from the bot with the German translation (e.g. “Hallo, wie geht es dir?”).

**Sanity checks**

- **Health**: Open `http://localhost:8000/health` in a browser (or `curl http://localhost:8000/health`). You should get `{"status":"ok"}`.
- **URL verification**: When you save the Request URL in Slack, the app must be running and reachable via ngrok. If it fails, check that the app is running, ngrok is pointing at 8000, and the URL ends with `/slack/events`.

### Optional: limit to one channel

In Slack, get the channel ID (right‑click the channel → **View channel details** → copy the ID from the bottom of the page, or from the channel URL). In `.env` set e.g.:

```bash
SLACK_CHANNEL_IDS=C01234ABCDE
```

Restart the app. Only that channel will be translated.

---

## Endpoints

- `POST /slack/events` – Slack Events API (url_verification + message events).
- `GET /health` – Health check.

## Behaviour

- **Language detection**: Only messages detected as English are translated; others are ignored.
- **Idempotency**: Duplicate events (e.g. Slack retries) are detected so the same message is not translated twice.
- **Bot messages** and **message subtypes** (e.g. channel_join, edits) are ignored.
