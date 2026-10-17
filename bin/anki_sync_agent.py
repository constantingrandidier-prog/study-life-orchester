import sys
import os
import time
import json
import ssl
import urllib.request
import subprocess
from pathlib import Path

import ctypes
import traceback

# Unconditionally redirect stdout and stderr to log file for background execution
_log_p = Path(__file__).resolve().parent / "anki_sync.log"
try:
    _log_file = open(_log_p, "a", encoding="utf-8", buffering=1)
    sys.stdout = _log_file
    sys.stderr = _log_file
except Exception:
    pass

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
        req = urllib.request.Request("http://127.0.0.1:8000/docs", method="HEAD")
        with urllib.request.urlopen(req, timeout=0.3):
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
        res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq anki.exe"], capture_output=True, text=True, errors="ignore")
        if "anki.exe" in res.stdout.lower():
            # Process is running; wait briefly for AnkiConnect to respond
            for _ in range(5):
                time.sleep(1.0)
                if is_ankiconnect_alive():
                    return True
            # If anki.exe is running but AnkiConnect never responds, process is frozen/zombie -> kill and restart
            log_msg("[AUTO-START] Anki-Prozess antwortet nicht (Zombie/Freeze) -> erzwinge Neustart...")
            subprocess.run(["taskkill", "/F", "/IM", "anki.exe"], capture_output=True, errors="ignore")
            time.sleep(1.0)
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


def trigger_anki_desktop_sync(timeout: float = 30.0) -> bool:
    """
    Trigger Anki Desktop's native synchronization with AnkiWeb via AnkiConnect.
    This pulls the latest card reviews/progress from the iPad/AnkiWeb down into the
    local collection.anki2 SQLite database completely silently without any popups!
    Uses 'multi' with barrier so that the true sync status is waited for and verified.
    If an editorConflict or blocking dialog is detected, gracefully restarts Anki Desktop.
    """
    if not is_ankiconnect_alive():
        ensure_anki_desktop_running()
        time.sleep(2.0)
        if not is_ankiconnect_alive():
            return False

    def _call_sync():
        req = urllib.request.Request(
            "http://127.0.0.1:8765",
            data=json.dumps({
                "action": "multi",
                "version": 6,
                "params": {"actions": [{"action": "sync"}]}
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = _call_sync()
        top_err = data.get("error")
        results = data.get("result") or []
        first_err = results[0].get("error") if (results and isinstance(results[0], dict)) else None
        err = top_err or first_err

        if not err:
            log_msg("[ANKI-SYNC] Anki Desktop mit AnkiWeb synchronisiert (iPad-Reviews geladen).")
            return True

        err_str = str(err).lower()
        if "close editors" in err_str or "editorconflict" in err_str:
            log_msg(f"[ANKI-SYNC] Editor-Konflikt in Anki Desktop ({err}) -> Starte Anki Desktop sauber neu...")
            try:
                exit_req = urllib.request.Request(
                    "http://127.0.0.1:8765",
                    data=json.dumps({"action": "guiExitAnki", "version": 6}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(exit_req, timeout=5.0):
                    pass
            except Exception:
                subprocess.run(["taskkill", "/F", "/IM", "anki.exe"], capture_output=True, errors="ignore")

            time.sleep(2.0)
            ensure_anki_desktop_running()
            time.sleep(2.5)

            if is_ankiconnect_alive():
                retry_data = _call_sync()
                retry_res = retry_data.get("result") or []
                retry_err = retry_data.get("error") or (retry_res[0].get("error") if (retry_res and isinstance(retry_res[0], dict)) else None)
                if not retry_err:
                    log_msg("[ANKI-SYNC] Nach Neustart: Anki Desktop erfolgreich mit AnkiWeb synchronisiert.")
                    return True
                else:
                    log_msg(f"[ANKI-SYNC] Nach Neustart Sync-Warnung: {retry_err}")
                    return False
        else:
            log_msg(f"[ANKI-SYNC] AnkiConnect sync warning: {err}")
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


_last_history_sync_date = None

def sync_now(trigger_anki_sync: bool = True):
    global _last_history_sync_date
    from datetime import date, timedelta
    targets = [RENDER_BASE]
    if is_local_server_running():
        targets.append(LOCAL_BASE)

    # 0. Silently trigger Anki Desktop to sync with AnkiWeb (pulls iPad reviews down to PC!)
    if trigger_anki_sync:
        synced = trigger_anki_desktop_sync()
        if synced:
            time.sleep(0.5)  # Wait for SQLite file lock/write buffers to settle

    # 1. Sync yesterday once per day to ensure rollover from iPad/midnight is clean
    today = date.today()
    if _last_history_sync_date != today:
        try:
            yesterday_str = (today - timedelta(days=1)).isoformat()
            yesterday_state = read_live_anki_desktop_state(target_date_str=yesterday_str)
            for base in targets:
                post_json(f"{base}/desktop-sync", yesterday_state, timeout=10.0)
            _last_history_sync_date = today
        except Exception as e:
            log_msg(f"[WARN] Yesterday sync note: {e}")

    # 2. Sync today's live state
    try:
        state = read_live_anki_desktop_state()
        for base in targets:
            post_json(f"{base}/desktop-sync", state)
    except Exception as e:
        log_msg(f"[ERROR] Today sync error: {e}")
        state = {}

    # 3. Sync 14-day workload forecast
    try:
        forecast = get_workload_forecast()
        for base in targets:
            post_json(f"{base}/workload-sync", forecast)
    except Exception as e:
        log_msg(f"[ERROR] Forecast sync error: {e}")
        forecast = {}

    # 4. Sync topic triage
    try:
        triage = calculate_backlog_triage()
        for base in targets:
            post_json(f"{base}/triage-sync", triage)
    except Exception as e:
        log_msg(f"[ERROR] Triage sync error: {e}")

    # 5. Sync weaknesses & full deck tree
    try:
        from app.services.anki_weakness_service import get_anki_due_and_weaknesses
        weaknesses = get_anki_due_and_weaknesses()
        for base in targets:
            post_json(f"{base}/weaknesses-sync", weaknesses)
    except Exception as e:
        log_msg(f"[ERROR] Weakness sync error: {e}")

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
        with open(_log_p, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


_INSTANCE_MUTEX = None
ERROR_ALREADY_EXISTS = 183

def acquire_single_instance_lock():
    """Ensure only one instance of anki_sync_agent runs concurrently using Windows Named Mutex."""
    global _INSTANCE_MUTEX
    try:
        mutex_name = "Global\\StudyLifeAnkiSyncAgentMutex"
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            if mutex:
                ctypes.windll.kernel32.CloseHandle(mutex)
            return None
        _INSTANCE_MUTEX = mutex
        return mutex
    except Exception as e:
        log_msg(f"[WARN] Mutex creation note: {e}")
        return True


if __name__ == "__main__":
    try:
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
            except Exception as e:
                log_msg(f"[WARN] Initial sync note: {e}")

            while True:
                try:
                    now = time.time()
                    file_changed = False
                    if not col or not col.exists():
                        col = find_local_anki_collection()

                    if col and col.exists():
                        wal = col.with_name(col.name + "-wal")
                        wal_m = wal.stat().st_mtime if wal.exists() else 0
                        m = max(col.stat().st_mtime, wal_m)
                        if last_mtime == 0:
                            last_mtime = m
                        elif m != last_mtime:
                            last_mtime = m
                            file_changed = True

                    # Every 60s: trigger AnkiWeb sync (pulls iPad progress) + push metrics to cloud
                    # If local file changed (WAL updated from reviews): push immediately without extra AnkiWeb trigger
                    if now - last_periodic >= 60:
                        sync_now(trigger_anki_sync=True)
                        last_periodic = now
                        if col and col.exists():
                            wal = col.with_name(col.name + "-wal")
                            wal_m = wal.stat().st_mtime if wal.exists() else 0
                            last_mtime = max(col.stat().st_mtime, wal_m)
                    elif file_changed:
                        log_msg("[LIVE-TRIGGER] Lokale Anki-Aktivitaet (WAL) erkannt -> Synchronisiere sofort...")
                        sync_now(trigger_anki_sync=False)
                        last_periodic = now
                except Exception as exc:
                    log_msg(f"[ERROR] Sync loop exception: {exc}")
                time.sleep(2)
    except Exception as fatal:
        log_msg(f"[FATAL] Sync agent crashed: {fatal}\n{traceback.format_exc()}")
