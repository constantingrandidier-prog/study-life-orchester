"""SWITCHcast / Kaltura downloader service for UZH medical lectures."""

import re
import json
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

DEFAULT_PODCAST_DIR = Path(r"c:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app\Podcasts")

def extract_switchcast_ids(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extracts entryId, flavorId, and ks token from a Kaltura URL."""
    entry_match = re.search(r"entryId/([a-zA-Z0-9_]+)", url)
    entry_id = entry_match.group(1) if entry_match else None
    
    flavor_match = re.search(r"flavorIds?/([a-zA-Z0-9_]+)", url)
    flavor_id = flavor_match.group(1) if flavor_match else None

    ks_match = re.search(r"/ks/([a-zA-Z0-9_-]+)", url)
    ks = ks_match.group(1) if ks_match else None

    return entry_id, flavor_id, ks

def get_lecture_title(entry_id: str, ks: Optional[str] = None) -> str:
    """Retrieves lecture name from the Kaltura API if session token is available."""
    if not ks:
        return entry_id
    try:
        api_url = f"https://api.cast.switch.ch/api_v3/service/baseentry/action/get?format=1&entryId={entry_id}&ks={ks}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            name = data.get("name")
            if name:
                return re.sub(r'[\\/*?:"<>|]', "_", name).strip()
    except Exception:
        pass
    return entry_id

def download_switchcast_lecture(url: str, output_dir: Path = DEFAULT_PODCAST_DIR) -> dict:
    """Downloads lecture directly from SWITCHcast VOD CDN without auth requirement."""
    output_dir.mkdir(parents=True, exist_ok=True)
    entry_id, flavor_id, ks = extract_switchcast_ids(url)
    
    if not entry_id:
        return {"success": False, "error": "Keine entryId im Link gefunden"}

    if not flavor_id:
        flavor_id = "0_yn9reccu"

    title = get_lecture_title(entry_id, ks)
    output_file = output_dir / f"{title}.mp4"
    if output_file.exists():
        output_file = output_dir / f"{title} [{entry_id}].mp4"
    
    direct_url = f"https://vod.kaltura.switch.ch/p/106/sp/10600/serveFlavor/entryId/{entry_id}/v/12/ev/6/flavorId/{flavor_id}/name/a.mp4"

    req = urllib.request.Request(direct_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024
        downloaded = 0
        with open(output_file, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)

    return {
        "success": True,
        "title": title,
        "filename": output_file.name,
        "file_path": str(output_file),
        "size_mb": round(downloaded / (1024 * 1024), 1)
    }
