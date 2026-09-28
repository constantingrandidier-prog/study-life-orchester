import os
import subprocess
from pathlib import Path

def setup_autostart():
    vbs_path = Path(os.environ.get("APPDATA")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "StudyLifeAnkiSync.vbs"
    print("VBS path:", vbs_path)
    
    # 1. Ensure Startup VBS exists
    root_dir = Path(__file__).resolve().parent.parent
    pythonw = root_dir / ".venv" / "Scripts" / "pythonw.exe"
    agent = root_dir / "bin" / "anki_sync_agent.py"
    
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
rootDir = "{root_dir}"
pythonwPath = "{pythonw}"
agentPath = "{agent}"
WshShell.CurrentDirectory = rootDir
WshShell.Run """" & pythonwPath & """ """ & agentPath & """", 0, False
'''
    vbs_path.write_text(vbs_content, encoding="utf-8")
    print("Startup folder VBS created successfully.")

    # 2. Also register a Windows Scheduled Task as a watchdog
    cmd = [
        "schtasks", "/create",
        "/tn", "StudyLifeAnkiSync",
        "/tr", f'wscript.exe "{vbs_path}"',
        "/sc", "ONLOGON",
        "/f"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("schtasks code:", res.returncode, "stdout:", res.stdout.strip(), "stderr:", res.stderr.strip())

if __name__ == "__main__":
    setup_autostart()
