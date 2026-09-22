FROM python:3.11-slim-bookworm

ARG TARGETARCH=amd64
ARG YTDLGO_VERSION=1.0.0

WORKDIR /app

# ytdlgo invokes yt-dlp, Deno and ffmpeg; Python build tools cover wheels that
# are unavailable on a deployment platform.
RUN test "$TARGETARCH" = "amd64" \
    || (echo "AlexaInc/ytdlgo 1.0.0 only publishes amd64 binaries" >&2; exit 1) \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl unzip ffmpeg gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Deno is used by current yt-dlp releases for YouTube JavaScript challenges.
RUN curl -fsSL --retry 5 \
      https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip \
      -o /tmp/deno.zip \
    && unzip -q /tmp/deno.zip -d /usr/local/bin \
    && chmod 0755 /usr/local/bin/deno \
    && rm /tmp/deno.zip

# Install and checksum-verify the requested ytdlgo release assets.
COPY scripts/install_ytdlgo.sh /usr/local/bin/install-ytdlgo
RUN YTDLGO_VERSION="$YTDLGO_VERSION" /usr/local/bin/install-ytdlgo /app/bin \
    && curl -fsSL --retry 5 \
       https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux \
       -o /app/bin/yt-dlp \
    && chmod 0755 /app/bin/yt-dlp \
    && ln -s /usr/local/bin/deno /app/bin/deno \
    && ln -s /usr/bin/ffmpeg /app/bin/ffmpeg \
    && ln -s /usr/bin/ffprobe /app/bin/ffprobe

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PATH="/app/bin:${PATH}" \
    YTDL_BIN=/app/bin/ytdl \
    YTDL_BIN_DIR=/app/bin \
    YTDLP_BIN=/app/bin/yt-dlp \
    DENO_BIN=/app/bin/deno \
    FFMPEG_BIN=/app/bin/ffmpeg \
    XET_UPLOAD_BIN=/app/bin/xet-upload \
    WORK_DIR=/tmp/ytdl-work \
    DOWNLOAD_DIR=/tmp/downloads \
    YTDL_RELAYS=""

# Fail the image build if the release or one of its required tools is unusable.
RUN /app/bin/ytdl doctor > /tmp/ytdl-doctor.json \
    && cat /tmp/ytdl-doctor.json \
    && python -c 'import json; d=json.load(open("/tmp/ytdl-doctor.json")); assert d.get("ok") and d.get("ytdlp") and d.get("ffmpeg") and d.get("xet_upload"), d'

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --requirement requirements.txt

# Build the checked-out project (including local changes); do not clone master
# from inside the image and accidentally discard those changes.
COPY . .

RUN useradd --create-home --uid 10014 choreouser \
    && mkdir -p "$WORK_DIR" "$DOWNLOAD_DIR" \
    && chown -R 10014:10014 /app "$WORK_DIR" "$DOWNLOAD_DIR"

USER 10014
EXPOSE 7860
CMD ["python3", "-m", "alexa"]
