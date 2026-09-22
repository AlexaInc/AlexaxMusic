import asyncio
from alexa.core.youtube import YouTube

async def test_search():
    yt = YouTube()
    track = await yt.search("Lana Del Rey Summertime Sadness", 12345)
    
    if track:
        print("Success!")
        print(f"Title: {track.title.encode('utf-8', 'ignore').decode('utf-8')}")
        print(f"Duration: {track.duration} ({track.duration_sec}s)")
        print(f"URL: {track.url}")
        print(f"Thumb: {track.thumbnail}")
        print(f"Channel: {track.channel_name.encode('utf-8', 'ignore').decode('utf-8')}")
        print(f"Views: {track.view_count}")
    else:
        print("Failed to find track.")

if __name__ == "__main__":
    asyncio.run(test_search())
