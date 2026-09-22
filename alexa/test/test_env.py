from os import getenv
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Get PROXY_URL from environment
proxy_url = getenv("PROXY_URL")

if proxy_url:
    print(f"✅ Successfully retrieved PROXY_URL: {proxy_url}")
else:
    print("❌ PROXY_URL not found in environment.")
