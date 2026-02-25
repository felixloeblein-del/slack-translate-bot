# Slack EN->DE translate bot – run 24/7 on Railway, Render, Fly.io, etc.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY slack_translate_bot/ ./slack_translate_bot/

# App reads PORT from env (e.g. Railway/Render set PORT=8000)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn slack_translate_bot.main:app --host 0.0.0.0 --port ${PORT}"]
