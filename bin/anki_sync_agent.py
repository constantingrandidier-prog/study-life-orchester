import sys
import os
import time
import json
import ssl
import urllib.request
import subprocess
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


def is_ankiconnect_alive(timeout: float = 0.8) -> bool:
    """Check if Anki Desktop is running with the AnkiConnect add-on responding."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8765",
            data=json.dumps({"action": "version", "version": 6}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result") is not None
    except Exception:
        return False


def ensure_anki_desktop_running():
    """Ensure Anki Desktop is running. If closed, launch minimized without stealing focus."""
    if is_ankiconnect_alive():
        return True

    # Check if anki.exe process is already active
    try:
        res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq anki.exe"], capture_output=True, text=True)
        if "anki.exe" in res.stdout.lower():
            return True
    except Exception:
        pass

    # Search for anki.exe in standard installation paths
    anki_paths = [
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\Anki\anki.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES%\Anki\anki.exe")),
        Path(os.path.expandvars(r"%PROGRAMFILES(X86)%\Anki\anki.exe")),
    ]
    for p in anki_paths:
        if p.exists():
            try:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = 7  # SW_SHOWMINNOACTIVE (minimized in taskbar, absolutely no focus stealing)
                DETACHED = 0x00000008
                subprocess.Popen([str(p)], startupinfo=si, creationflags=DETACHED)
                log_msg("[AUTO-START] Anki Desktop im Hintergrund minimiert gestartet.")
                return True
            except Exception as e:
                log_msg(f"[AUTO-START] Fehler beim Starten von Anki: {e}")
                return False
    return False


def trigger_anki_desktop_sync(timeout: float = 25.0) -> bool:
    """
    Trigger Anki Desktop's native synchronization with AnkiWeb via AnkiConnect.
    This pulls the latest card reviews/progress from the iPad/AnkiWeb down into the
    local collection.anki2 SQLite database completely silently without any popups!
    """
    if not is_ankiconnect_alive():
        ensure_anki_desktop_running()
        time.sleep(1.0)
        if not is_ankiconnect_alive():
            return False

    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8765",
            data=json.dumps({"action": "sync", "version": 6}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("error"):
                log_msg("[ANKI-SYNC] Anki Desktop mit AnkiWeb synchronisiert (iPad-Reviews geladen).")
                return True
            else:
                log_msg(f"[ANKI-SYNC] AnkiConnect sync warning: {data.get('error')}")
                return False
    except Exception as exc:
        log_msg(f"[ANKI-SYNC] Sync note: {exc}")
        return False


def post_json(url: str, data_dict: dict, timeout: float = 25.0) -> bool:
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


def sync_now(trigger_anki_sync: bool = True):
    from datetime import date, timedelta
    targets = [RENDER_BASE]
    if is_local_server_running():
        targets.append(LOCAL_BASE)

    # 0. Silently trigger Anki Desktop to sync with AnkiWeb (pulls iPad reviews down to PC!)
    if trigger_anki_sync:
        synced = trigger_anki_desktop_sync()
        if synced:
            time.sleep(0.5)  # Wait for SQLite file lock/write buffers to settle

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

    # 6. Sync comprehensive deck stats & retention
    try:
        from app.services.anki_deck_stats import get_detailed_deck_stats
        deck_stats = get_detailed_deck_stats()
        for base in targets:
            ok = post_json(f"{base}/deck-retention-sync", deck_stats, timeout=25.0)
            if not ok:
                log_msg(f"[WARN] deck-retention-sync failed to {base}")
    except Exception as e:
        log_msg(f"[ERROR] Deck stats sync error: {e}")

    revs = state.get("today_reviewed_count", 0)
    opened = state.get("new_cards_opened_count", revs)
    learning = state.get("new_cards_in_learning_count", 0)
    reps = state.get("repetition_cards_count", 0)
    due_today = state.get("due_today_count", 0)
    due_tom = state.get("due_tomorrow_count", 0)
    log_msg(f"[SYNC-OK] Render synced: {due_today} Faellig heute, {revs} Neu gemeistert ({learning} in Lernphase, {opened} aufgemacht), {reps} Wiederholungen, {due_tom} morgen faellig.")


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
        sync_now(trigger_anki_sync=True)
    else:
        lock = acquire_single_instance_lock()
        if lock is None:
            # Another instance is already running silently in background
            sys.exit(0)

        col = find_local_anki_collection()
        last_mtime = 0
        last_periodic = 0
        log_msg("[START] Anki Live Sync Agent running (Silent background AnkiWeb & Render data sync)...")
        try:
            sync_now(trigger_anki_sync=True)
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

                # Every 60s: trigger AnkiWeb sync (pulls iPad progress) + push metrics to cloud
                # If local file changed outside periodic sync: push immediately without extra AnkiWeb trigger
                if now - last_periodic >= 60:
                    sync_now(trigger_anki_sync=True)
                    last_periodic = now
                    if col and col.exists():
                        last_mtime = col.stat().st_mtime
                elif file_changed:
                    sync_now(trigger_anki_sync=False)
                    last_periodic = now
            except Exception as exc:
                print(f"Sync loop note: {exc}", flush=True)
            time.sleep(2)
