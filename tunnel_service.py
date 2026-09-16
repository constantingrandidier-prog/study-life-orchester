"""
Study-Life-Orchester Tunnel Service
Manages remote access via Cloudflare Tunnel (Fixed Domain via Token or Quick Tunnel).
"""
import os
import sys
import re
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CLOUDFLARED_BIN = BASE_DIR / "bin" / "cloudflared.exe"

def get_tunnel_command():
    token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "").strip()
    if token:
        # Fixed domain tunnel managed via Cloudflare Zero Trust
        return [str(CLOUDFLARED_BIN), "tunnel", "run", "--token", token]
    else:
        # Quick tunnel fallback
        return [str(CLOUDFLARED_BIN), "tunnel", "--url", "http://127.0.0.1:8000"]

if __name__ == "__main__":
    if not CLOUDFLARED_BIN.exists():
        print(f"Error: cloudflared binary not found at {CLOUDFLARED_BIN}")
        sys.exit(1)
    
    cmd = get_tunnel_command()
    print(f"Starting tunnel with command: {' '.join(cmd[:3])}...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    found_url = None
    
    for line in proc.stdout:
        print(line, end="")
        if not found_url:
            match = url_pattern.search(line)
            if match:
                found_url = match.group(0)
                print("\n" + "=" * 60)
                print(f"ONLINE! Mobile URL: {found_url}/app")
                print("=" * 60 + "\n")
