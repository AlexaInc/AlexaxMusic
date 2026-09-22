import asyncio
import httpx
import json
import subprocess

async def main():
    with open("alexa/helpers/channels.json", "r", encoding="utf-8") as f:
        channels = json.load(f)
    channel = channels[0]
    
    print(f"Testing {channel['title']}...")
    manifest_url = channel["manifest"]
    
    from config import Config
    c = Config()
    
    async with httpx.AsyncClient(proxy=c.PROXY_URL) as client:
        resp = await client.get(manifest_url)
        data = resp.json()
        
    url = data['data']['url']
    print(f"Got M3U8 URL: {url}")
    
    print("Running ffprobe...")
    cmd = [
        'ffprobe', 
        '-v', 'error', 
        '-show_entries', 'stream=width,height,codec_type,codec_name', 
        '-show_format', 
        '-of', 'json', 
        url
    ]
    
    # We set env to mimic PyTgCalls with http_proxy
    import os
    env = os.environ.copy()
    env["http_proxy"] = c.PROXY_URL
    env["https_proxy"] = c.PROXY_URL
    
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    print("STDOUT:", proc.stdout)
    print("STDERR:", proc.stderr)

if __name__ == "__main__":
    asyncio.run(main())
