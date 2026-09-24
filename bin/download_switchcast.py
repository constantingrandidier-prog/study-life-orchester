"""Automated SWITCHcast / Kaltura podcast downloader for UZH lectures."""

import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from app.services.switchcast_service import download_switchcast_lecture

if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Starte Download fuer:\n{url}\n")
        res = download_switchcast_lecture(url)
        if res.get("success"):
            print(f"\n[ERFOLG] {res.get('title')} ({res.get('size_mb')} MB) gespeichert in:\n{res.get('file_path')}")
        else:
            print(f"\n[FEHLER] {res.get('error')}")
    else:
        print("Verwendung: python download_switchcast.py <SWITCHCAST_URL>")
