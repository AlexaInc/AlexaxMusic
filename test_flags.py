import asyncio
from alexa import player
from pytgcalls import types
from alexa.helpers._dataclass import Track
from unittest.mock import AsyncMock, MagicMock

async def main():
    media_obj = Track(
        id="tv_live",
        channel_name="Live TV",
        duration="Live",
        duration_sec=0,
        title=f"TV: Test",
        url="http://test",
        file_path="http://test",
        message_id=1,
        video=True
    )
    media_obj.stream_type = "live"
    media_obj.quality = "low"
    media_obj.headers = {"User-Agent": "test"}

    # Mock types.MediaStream
    original_ms = types.MediaStream
    
    def mock_ms(*args, **kwargs):
        print("--- Called MediaStream! ---")
        print("audio_flags:", kwargs.get('audio_flags'))
        print("video_flags:", kwargs.get('video_flags'))
        return original_ms(*args, **kwargs)
        
    import pytgcalls.types.stream.media_stream
    pytgcalls.types.stream.media_stream.MediaStream = mock_ms
    import alexa.core.calls
    alexa.core.calls.types.MediaStream = mock_ms

    msg = MagicMock()
    msg.edit_text = AsyncMock()

    # Mock client play
    try:
        await player.play_media(chat_id=123, message=msg, media=media_obj)
    except Exception as e:
        print("Caught exception or aborted:", type(e))

if __name__ == "__main__":
    asyncio.run(main())
