import subprocess
import sys
from pathlib import Path

def setup_watchdog():
    root_dir = Path(__file__).resolve().parent.parent
    pythonw_path = root_dir / ".venv" / "Scripts" / "pythonw.exe"
    agent_path = root_dir / "bin" / "anki_sync_agent.py"
    
    tr_cmd = f'"{pythonw_path}" "{agent_path}" --once'

    # 1. Remove old morning/evening tasks
    subprocess.run(["schtasks", "/Delete", "/TN", "StudyLifeAnkiSync_Morning", "/F"], capture_output=True)
    subprocess.run(["schtasks", "/Delete", "/TN", "StudyLifeAnkiSync_Evening", "/F"], capture_output=True)
    print("Old fixed-hour tasks removed.")

    # 2. Register every-10-minutes watchdog task
    res = subprocess.run([
        "schtasks", "/Create", "/F",
        "/SC", "MINUTE",
        "/MO", "10",
        "/TN", "StudyLifeAnkiSync_Periodic",
        "/TR", tr_cmd
    ], capture_output=True, text=True)
    print("Periodic 10-min Task:", res.stdout.strip() or res.stderr.strip())

if __name__ == "__main__":
    setup_watchdog()
