import os
import sys

# Mocking Config and other dependencies if needed, or just import and test
# For simplicity, we'll try to import the actual config and test it.

# Add the project root to sys.path
sys.path.append(os.getcwd())

def test_proxy():
    # Test case 1: No proxy
    os.environ["PROXY_URL"] = ""
    from config import Config
    config = Config()
    print(f"Test 1 (Empty Proxy): {config.PROXY == None}")

    # Test case 2: HTTP Proxy
    os.environ["PROXY_URL"] = "http://user:pass@1.2.3.4:8080"
    config = Config() # Reloading might be tricky due to singleton-like usage, but let's see
    # Actually, we should call _parse_proxy directly for better testing
    parsed = config._parse_proxy("http://user:pass@1.2.3.4:8080")
    print(f"Test 2 (HTTP Proxy): {parsed == {'scheme': 'http', 'hostname': '1.2.3.4', 'port': 8080, 'username': 'user', 'password': 'pass'}}")

    # Test case 3: SOCKS5 Proxy
    parsed = config._parse_proxy("socks5://5.6.7.8:1080")
    print(f"Test 3 (SOCKS5 Proxy): {parsed == {'scheme': 'socks5', 'hostname': '5.6.7.8', 'port': 1080, 'username': None, 'password': None}}")

    # Test case 4: Invalid Scheme
    parsed = config._parse_proxy("ftp://1.2.3.4")
    print(f"Test 4 (Invalid Scheme): {parsed == None}")

if __name__ == "__main__":
    test_proxy()
