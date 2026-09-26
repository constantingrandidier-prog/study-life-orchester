import sys
import os
import time
import json
import ssl
import urllib.request
from pathlib import Path

# Redirect stdout and stderr for pythonw.exe (windowless mode on Windows)
_log_p = Path(__file__).resolve().parent / "anki_sync.log"
try:
    if sys.stdout is None:
        sys.stdout = open(_log_p, "a", encoding="utf-8", buffering=1)
    else:
        sys.stdout.write("")
except Exception:
    sys.stdout = open(_log_p, "a", encoding="utf-8", buffering=1)

try:
    if sys.stderr is None:
        sys.stderr = sys.stdout
    else:
        sys.stderr.write("")
except Exception:
    sys.stderr = sys.stdout

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.anki_desktop_sync import read_live_anki_desktop_state, find_local_anki_collection
from app.services.anki_backlog_triage import calculate_backlog_triage
from app.services.workload_forecast import get_workload_forecast

RENDER_BASE = "https://study-life-orchester.onrender.com/api/v1/schedule/anki"
LOCAL_BASE = "http://127.0.0.1:8000/api/v1/schedule/anki"

# Create SSL context that accepts self-signed/proxy certs (Pulse Secure / campus VPN)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

def is_local_server_running() -> bool:
    try:
        import socket
        with socket.create_connection(("127.0.0.1", 8000), timeout=0.2):
            return True
    except Exception:
        return False

def post_json(url: str, data_dict: dict, timeout: float = 6.0) -> bool:
    try:
        payload = json.dumps(data_dict).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "AnkiLiveSyncAgent/2.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        return False

def sync_now():
    from datetime import date, timedelta
    targets = [RENDER_BASE]
    if is_local_server_running():
        targets.append(LOCAL_BASE)

    # 1. Sync all past days since semester start (ensures cumulative backlog is always 100% accurate)
    try:
        sem_start = date(2026, 9, 14)
        curr = sem_start
        while curr < date.today():
            past_str = curr.isoformat()
            past_state = read_live_anki_desktop_state(target_date_str=past_str)
            for base in targets:
                post_json(f"{base}/desktop-sync", past_state)
            curr += timedelta(days=1)
    except Exception as e:
        print("Semester history sync error:", e, flush=True)


    # 2. Sync today's state
    try:
        state = read_live_anki_desktop_state()
        for base in targets:
            post_json(f"{base}/desktop-sync", state)
    except Exception as e:
        print("Today sync error:", e, flush=True)
        state = {}

    # 3. Sync 14-day workload forecast
    try:
        forecast = get_workload_forecast()
        for base in targets:
            post_json(f"{base}/workload-sync", forecast)
    except Exception as e:
        print("Forecast sync error:", e, flush=True)
        forecast = {}

    # 4. Sync topic triage
    try:
        triage = calculate_backlog_triage()
        for base in targets:
            post_json(f"{base}/triage-sync", triage)
    except Exception as e:
        print("Triage sync error:", e, flush=True)

    # 5. Sync weaknesses & full deck tree
    try:
        from app.services.anki_weakness_service import get_anki_due_and_weaknesses
        weaknesses = get_anki_due_and_weaknesses()
        for base in targets:
            post_json(f"{base}/weaknesses-sync", weaknesses)
    except Exception as e:
        print("Weakness sync error:", e, flush=True)

    revs = state.get("today_reviewed_count", 0)
    reps = state.get("repetition_cards_count", 0)
    due_today = state.get("due_today_count", 0)
    due_tom = state.get("due_tomorrow_count", 0)
    log_msg(f"[SYNC-OK] Render synced: {due_today} Faellig heute, {revs} Neu gelernt, {reps} Wiederholungen, {due_tom} morgen faellig.")

def log_msg(msg: str):
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now_str}] {msg}\n"
    try:
        if sys.stdout and hasattr(sys.stdout, "write"):
            sys.stdout.write(line)
            sys.stdout.flush()
    except Exception:
        pass
    try:
        with open(_log_p, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


_INSTANCE_LOCK = None

def acquire_single_instance_lock():
    """Ensure only one instance of anki_sync_agent runs concurrently."""
    global _INSTANCE_LOCK
    lock_path = Path(__file__).resolve().parent / ".anki_sync.lock"
    try:
        import msvcrt
        f = open(lock_path, "a+")
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            _INSTANCE_LOCK = f
            return f
        except (IOError, OSError):
            return None
    except Exception:
        return None


if __name__ == "__main__":
    if "--once" in sys.argv:
        sync_now()
    else:
        lock = acquire_single_instance_lock()
        if lock is None:
            # Another instance is already running silently in background
            sys.exit(0)

        col = find_local_anki_collection()
        last_mtime = 0
        last_periodic = 0
        log_msg("[START] Anki Live Sync Agent running (Silent background data sync)...")
        try:
            sync_now()
            last_periodic = time.time()
        except Exception:
            pass

        while True:
            try:
                now = time.time()
                file_changed = False
                if not col or not col.exists():
                    col = find_local_anki_collection()

                if col and col.exists():
                    m = col.stat().st_mtime
                    if m != last_mtime:
                        last_mtime = m
                        file_changed = True

                # Sync if database changed OR every 60 seconds periodically
                if file_changed or (now - last_periodic >= 60):
                    sync_now()
                    last_periodic = now
            except Exception as exc:
                print(f"Sync loop note: {exc}", flush=True)
            time.sleep(2)

