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

    # 2. Register every-10-minutes watchdog task
    res = subprocess.run([
        "schtasks", "/Create", "/F",
        "/SC", "MINUTE",
        "/MO", "10",
        "/TN", "StudyLifeAnkiSync_Periodic",
        "/TR", tr_cmd
    ], capture_output=True, text=True)

    # 3. Modify XML to allow running on battery without AC restriction
    xml_res = subprocess.run(["schtasks", "/Query", "/TN", "StudyLifeAnkiSync_Periodic", "/XML"], capture_output=True)
    if xml_res.returncode == 0 and xml_res.stdout:
        xml_content = None
        for enc in ("utf-16", "utf-8", "cp1252"):
            try:
                xml_content = xml_res.stdout.decode(enc)
                break
            except Exception:
                continue
        if xml_content:
            xml_content = xml_content.replace("<DisallowStartIfOnBatteries>true</DisallowStartIfOnBatteries>", "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>")
            xml_content = xml_content.replace("<StopIfGoingOnBatteries>true</StopIfGoingOnBatteries>", "<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>")
            temp_xml = Path(__file__).resolve().parent / "task_temp.xml"
            temp_xml.write_text(xml_content, encoding="utf-16")
            subprocess.run(["schtasks", "/Create", "/F", "/TN", "StudyLifeAnkiSync_Periodic", "/XML", str(temp_xml)], capture_output=True)
            if temp_xml.exists():
                temp_xml.unlink()
            print("StudyLifeAnkiSync_Periodic configured: Runs every 10 mins (battery-friendly).")

if __name__ == "__main__":
    setup_watchdog()
