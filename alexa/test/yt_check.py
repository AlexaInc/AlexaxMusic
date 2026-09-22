import asyncio
import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.getcwd())

async def test_yt_download():
    from alexa.core.youtube import YouTube
    yt = YouTube()
    
    # Test video link (random popular video for testing)
    video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ" # Rick Astley for safety
    video_id = "aqz-KE-bpKQ"
    
    print(f"Testing CNV converter for: {video_url}")
    
    # 1. Test _get_cnv_key and _cnv_converter directly
    direct_url = await yt._cnv_converter(video_url, video=False)
    if direct_url:
        print(f"✅ CNV Success! Direct URL: {direct_url[:50]}...")
    else:
        print("❌ CNV Failed!")

if __name__ == "__main__":
    asyncio.run(test_yt_download())
