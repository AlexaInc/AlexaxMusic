FROM python:3.11-slim-bookworm

# 1. Set Working Directory
WORKDIR /app

# 2. Install System Dependencies
RUN apt-get update -y && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
    ffmpeg curl unzip git gcc python3-dev ca-certificates xz-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Deno (needed by yt-dlp >= 2026 for YouTube JS challenges)
RUN curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin && chmod 755 /usr/local/bin/deno && rm /tmp/deno.zip

# 4. Create User (Standard for Choreo/Cloud Run)
RUN useradd -m -u 10014 choreouser

# 5. Clone the Repository
RUN git clone https://github.com/AlexaInc/AlexaxMusic.git /tmp/alexa \
    && mv /tmp/alexa/* . \
    && rm -rf /tmp/alexa

# ----------------------------------------------------------------------
# 5b. ytdl toolchain -> /app/bin  (ytdl + xet-upload from AlexaInc/ytdlgo release, yt-dlp_linux)
#     youtube.py looks for <project>/bin/ytdl by default and prepends /app/bin to PATH.
# ----------------------------------------------------------------------
ARG YTDLGO_VERSION=1.0.0
RUN mkdir -p /app/bin \
    && curl -fsSL -o /app/bin/ytdl       https://github.com/AlexaInc/ytdlgo/releases/download/${YTDLGO_VERSION}/ytdl \
    && curl -fsSL -o /app/bin/xet-upload https://github.com/AlexaInc/ytdlgo/releases/download/${YTDLGO_VERSION}/xet-upload \
    && curl -fsSL -o /app/bin/yt-dlp     https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux \
    && ln -sf /usr/local/bin/deno /app/bin/deno \
    && ln -sf /usr/bin/ffmpeg  /app/bin/ffmpeg \
    && ln -sf /usr/bin/ffprobe /app/bin/ffprobe \
    && chmod 755 /app/bin/* \
    && /app/bin/ytdl doctor || true

# 6. Install Python Requirements
RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -U -r requirements.txt

# 7. Environment Variables
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/bin:${PATH}"
# ytdl runtime (secrets HF_TOKEN / COOKIES_URLS come from the platform's env, not the image)
ENV YTDL_BIN=/app/bin/ytdl
ENV YTDL_BIN_DIR=/app/bin
ENV HF_BUCKET=hazu165/songs
ENV WORK_DIR=/tmp/ytdl-work
ENV DOWNLOAD_DIR=/tmp/downloads
ENV YTDL_RELAYS=https://absolute-vonnie-alexainc-ec756816.koyeb.app

# ----------------------------------------------------------------------
# FIX 1: LOG FILE HACK (Redirecting writes to /tmp for Read-Only FS)
# ----------------------------------------------------------------------
RUN if [ -f anony/__init__.py ]; then \
    sed -i 's/"log.txt"/"\/tmp\/log.txt"/g' anony/__init__.py; \
    fi

# ----------------------------------------------------------------------
# FIX 2: EXPOSE A PORT
# ----------------------------------------------------------------------
EXPOSE 7860

# 8. Grant Permissions to the specific user
RUN chown -R 10014:10014 /app

# 9. Switch User
USER 10014

# 10. Start Bot
CMD ["python3", "-m", "anony"]
