import sys
import os
import time
import json
import ssl
import urllib.request
from pathlib import Path

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
    now_str = time.strftime("%H:%M:%S")
    print(
        f"[{now_str}] [SYNC-OK] Render synced: {due_today} Faellig heute, {revs} Neu gelernt, {reps} Wiederholungen, {due_tom} morgen faellig.",
        flush=True,
    )


def _launch_desktop_explorer(target_path_or_folder: Path):
    """Launches Windows Explorer directly onto the user's interactive desktop (WinSta0\\Default) and brings it to front."""
    import subprocess
    import ctypes
    from ctypes import wintypes
    import time

    target_str = str(target_path_or_folder).replace("/", "\\")
    is_file = target_path_or_folder.is_file()

    if is_file:
        cmd = f'explorer.exe /select,"{target_str}"'
    else:
        cmd = f'explorer.exe "{target_str}"'

    launched = False
    try:
        class STARTUPINFO(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR),
                ('lpTitle', wintypes.LPWSTR),
                ('dwX', wintypes.DWORD),
                ('dwY', wintypes.DWORD),
                ('dwXSize', wintypes.DWORD),
                ('dwYSize', wintypes.DWORD),
                ('dwXCountChars', wintypes.DWORD),
                ('dwYCountChars', wintypes.DWORD),
                ('dwFillAttribute', wintypes.DWORD),
                ('dwFlags', wintypes.DWORD),
                ('wShowWindow', wintypes.WORD),
                ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_void_p),
                ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE),
                ('hStdError', wintypes.HANDLE),
            ]

        class PROCESS_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('hProcess', wintypes.HANDLE),
                ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD),
                ('dwThreadId', wintypes.DWORD),
            ]

        si = STARTUPINFO()
        si.cb = ctypes.sizeof(STARTUPINFO)
        si.lpDesktop = 'WinSta0\\Default'
        pi = PROCESS_INFORMATION()

        res = ctypes.windll.kernel32.CreateProcessW(
            None, cmd, None, None, False, 0, None, None, ctypes.byref(si), ctypes.byref(pi)
        )
        if res:
            ctypes.windll.kernel32.CloseHandle(pi.hProcess)
            ctypes.windll.kernel32.CloseHandle(pi.hThread)
            launched = True
    except Exception:
        pass

    if not launched:
        if is_file:
            explorer_args = f'/select,\\"{target_str}\\"'
        else:
            explorer_args = f'\\"{target_str}\\"'
        task_cmd = f'explorer.exe {explorer_args}'
        create_cmd = f'schtasks /create /tn "StudyLifeOpen" /tr "{task_cmd}" /sc once /st 23:59 /f'
        subprocess.run(create_cmd, shell=True, capture_output=True)
        subprocess.run('schtasks /run /tn "StudyLifeOpen"', shell=True, capture_output=True)

    try:
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
            user32.AllowSetForegroundWindow(-1)
            time.sleep(0.3)
            
            def _enum_cb(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        if "Datei-Explorer" in title or "Explorer" in title or target_path_or_folder.name in title:
                            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                            user32.SetForegroundWindow(hwnd)
                            user32.BringWindowToTop(hwnd)
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
    except Exception:
        pass


_EXECUTED_ACTION_IDS = set()
_LAST_EXECUTED_PATH = ""
_LAST_EXECUTED_TIME = 0.0


def execute_desktop_action(act: dict):
    global _LAST_EXECUTED_PATH, _LAST_EXECUTED_TIME
    action_type = act.get("action", "open_explorer")
    act_id = act.get("id")
    import subprocess
    import time
    from pathlib import Path

    if act_id:
        if act_id in _EXECUTED_ACTION_IDS:
            return
        _EXECUTED_ACTION_IDS.add(act_id)
        if len(_EXECUTED_ACTION_IDS) > 200:
            _EXECUTED_ACTION_IDS.pop()

    if action_type == "stop_media":
        try:
            subprocess.run("taskkill /F /IM vlc.exe /T 2>nul", shell=True)
            print("[ACTION] Alle laufenden VLC/Audio-Prozesse erfolgreich beendet.", flush=True)
        except Exception as exc:
            print(f"[ACTION] Fehler beim Beenden von VLC: {exc}", flush=True)
        return

    raw_path = (act.get("path") or "").strip().replace("/", "\\")
    if not raw_path:
        return

    now_t = time.time()
    if raw_path == _LAST_EXECUTED_PATH and (now_t - _LAST_EXECUTED_TIME) < 2.5:
        print(f"[ACTION] Unterdrücke doppelten Aufruf innerhalb 2.5s: {raw_path}", flush=True)
        return
    _LAST_EXECUTED_PATH = raw_path
    _LAST_EXECUTED_TIME = now_t

    # Terminate any stray background VLC instances first
    try:
        subprocess.run("taskkill /F /IM vlc.exe /T 2>nul", shell=True)
    except Exception:
        pass

    import re
    target = None
    direct_p = Path(raw_path)
    if direct_p.exists():
        target = direct_p
    else:
        base_dirs = [
            Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop\UNI sem app"),
            Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\alles\Studium"),
            Path(r"C:\Users\Constantin Grandidie\OneDrive - Universität Zürich UZH\Desktop"),
        ]
        for b in base_dirs:
            if not b.exists():
                continue
            cand = b / raw_path
            if cand.exists():
                target = cand
                break
            cand_pod = b / "Podcasts" / raw_path
            if cand_pod.exists():
                target = cand_pod
                break
            fname = Path(raw_path).name
            matches = list(b.glob(f"**/{fname}"))
            if matches:
                target = matches[0]
                break
            m = re.search(r'([A-Za-z0-9_\-\.]+\.(?:pdf|mp4))', raw_path, re.IGNORECASE)
            if m:
                sub_matches = list(b.glob(f"**/*{m.group(1)}*"))
                if sub_matches:
                    target = sub_matches[0]
                    break

    if not target or not target.exists():
        print(f"[ACTION] Pfad lokal nicht gefunden: {raw_path}", flush=True)
        return

    try:
        if target.is_file():
            _launch_desktop_explorer(target)
            print(f"[ACTION] Datei im Windows Explorer markiert: {target.name}", flush=True)
        else:
            SLIDE_VIDEO_PREFERENCE = {
                "2025-09-18_TB_Blut_-_Immunsystem": "2025-09-18_TB_Blut_-_Immunsystem_Prof_Erklaerung.mp4",
                "2025-09-25_TB_Blut_-_Immunsystem": "2025-09-25_TB_Blut_-_Immunsystem_Prof_Erklaerung.mp4",
                "2025-09-26_TB_Blut_-_Immunsystem": "2025-09-26_TB_Blut_-_Immunsystem_Prof_Erklaerung.mp4",
            }
            target_file = None
            pref_name = SLIDE_VIDEO_PREFERENCE.get(target.name)
            if pref_name and (target / pref_name).exists():
                target_file = target / pref_name
            else:
                folien_vids = list(target.glob("*Folien*.mp4")) or list(target.glob("*.mp4")) or list(target.glob("*.pdf"))
                if folien_vids:
                    target_file = folien_vids[0]

            if target_file:
                _launch_desktop_explorer(target_file)
                print(f"[ACTION] Video/Folie im Explorer markiert: {target_file.name}", flush=True)
            else:
                _launch_desktop_explorer(target)
                print(f"[ACTION] Ordner im Explorer geöffnet: {target.name}", flush=True)
    except Exception as e:
        print(f"[ACTION] Fehler beim Ausführen: {e}", flush=True)



def check_and_execute_pending_actions():
    poll_url = "https://study-life-orchester.onrender.com/api/v1/schedule/system/poll-actions"
    try:
        req = urllib.request.Request(poll_url, headers={"User-Agent": "AnkiLiveSyncAgent/2.0"})
        with urllib.request.urlopen(req, timeout=2.0, context=SSL_CTX) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                for act in data.get("actions", []):
                    execute_desktop_action(act)
    except Exception:
        pass


if __name__ == "__main__":
    if "--once" in sys.argv:
        sync_now()
    else:
        col = find_local_anki_collection()
        last_mtime = 0
        last_periodic = 0
        print("[START] Anki Live Sync Agent running (Continuous & File-Watch mode)...", flush=True)
        sync_now()
        while True:
            try:
                check_and_execute_pending_actions()
                now = time.time()
                file_changed = False
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
                print(f"Sync loop error: {exc}", flush=True)
            time.sleep(1)

