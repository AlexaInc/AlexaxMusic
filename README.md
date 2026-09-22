# Alexa Music

Telegram group-call music bot, implemented by the `alexa` Python package, with a pinned [AlexaInc/ytdlgo 1.0.0](https://github.com/AlexaInc/ytdlgo/releases/tag/1.0.0) download backend.

## Download architecture

Every YouTube audio/video download now goes through one of these ytdlgo paths:

1. **Local (default):** `bin/ytdl get <video-id> --type audio|video`
2. **Optional relay:** ytdlgo's `POST /convert` API, configured with `YTDL_RELAYS`

There is no direct Python `yt-dlp` download fallback. The ytdlgo release invokes `yt-dlp`, Deno, and ffmpeg as its own toolchain. The Docker image downloads the exact `ytdl` and `xet-upload` 1.0.0 assets and verifies their published SHA-256 digests before building.

## Docker deployment (recommended)

```bash
cp .env.example .env
# Fill the required Telegram and MongoDB values in .env.
docker build --platform linux/amd64 -t alexamusic .
docker run --rm --env-file .env -p 7860:7860 alexamusic
```

The 1.0.0 release currently provides Linux x86-64 binaries, so the Docker build intentionally requires `linux/amd64`.

Check the bot health server at `http://localhost:7860/health`. During image build, `ytdl doctor` is also required to report working `yt-dlp`, ffmpeg, and `xet-upload` tools.

## Local installation

Python 3.11+, ffmpeg, curl, unzip, and an x86-64 Linux host are required.

```bash
# Install ytdlgo 1.0.0 and xet-upload with checksum verification.
./scripts/install_ytdlgo.sh ./bin

# Install current yt-dlp and Deno where ytdlgo can find them.
curl -fsSL https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux -o ./bin/yt-dlp
chmod 755 ./bin/yt-dlp
# Install Deno from https://docs.deno.com/runtime/getting_started/installation/

python3 -m pip install -r requirements.txt
cp .env.example .env
# Edit .env, then:
python3 -m alexa
```

Verify the real release and its dependencies:

```bash
PATH="$PWD/bin:$PATH" YTDLP_BIN="$PWD/bin/yt-dlp" ./bin/ytdl doctor
```

For an end-to-end test with media you are authorized to download, the CLI accepts:

```bash
PATH="$PWD/bin:$PATH" ./bin/ytdl get '<video-id-or-YouTube-URL>' --type audio
```

## Environment

`.env.example` documents every bot and ytdlgo setting. At minimum, configure:

- `API_ID`, `API_HASH`, `BOT_TOKEN`
- `MONGO_URL`, `LOGGER_ID`, `OWNER_ID`
- `SESSION`

The local ytdlgo backend needs no storage account. Leave `HF_BUCKET` and `HF_TOKEN` empty to keep results locally. Configure both to enable its Hugging Face Bucket cache.

`COOKIES_URLS` may contain comma/newline-separated URLs to Netscape cookie files. The release downloads and rotates them. Treat cookie URLs and files as secrets.

Relays are disabled by default. If you operate a ytdlgo HTTP service, set `YTDL_RELAYS`; if that service has `RELAY_SECRET`, set the same value as `YTDL_RELAY_KEY` in this bot.

Only download media you are authorized to access, and follow the source platform's terms and applicable law.
