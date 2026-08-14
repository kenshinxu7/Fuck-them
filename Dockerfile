# ──────────────────────────────────────────────────────────────
#  KENSHIN ANIME'S — Telegram Anime Search Bot
#  Base: python:3.11-slim-bookworm (Debian 12)
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm

# Metadata
LABEL maintainer="@KENSHIN_ANIME" \
      description="Telegram Anime Search Bot — Pyrogram + AniList"

# Prevent .pyc files and enable unbuffered stdout (see logs live)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── System dependencies (minimal) ─────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ──────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────
COPY bot.py .

# ── Runtime ───────────────────────────────────────────────────
# Pass secrets as env vars at runtime:
#   docker run -e API_ID=... -e API_HASH=... -e BOT_TOKEN=... kenshin-bot
CMD ["python", "bot.py"]
