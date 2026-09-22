import socket
import sys

host = "cool-shelia-alexainclk-91c1716d.koyeb.app"
port = 8888

print(f"Testing public connectivity to {host}:{port}...")
try:
    # DNS Check
    print(f"Resolving DNS for {host}...")
    ip = socket.gethostbyname(host)
    print(f"✅ DNS Resolved {host} to {ip}")
    
    # Connection Check
    print(f"Attempting to connect to {ip}:{port}...")
    s = socket.create_connection((ip, port), timeout=10)
    s.close()
    print("✅ Port is OPEN and reachable!")
except Exception as e:
    print(f"❌ Connectivity failed: {e}")
